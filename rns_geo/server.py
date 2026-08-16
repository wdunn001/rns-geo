"""rns-geo server: a Reticulum request-handler destination that answers compact
geo-data queries by calling the local .88 backends.

Design notes vs rns-time:
  * rns-time replies with a single tiny RNS.Packet. Geo answers are variable and
    can exceed one packet's MDU (a POI list, a route polyline), so we use RNS's
    request-handler API (destination.register_request_handler). RNS transparently
    delivers small responses as a packet and large ones as a Resource -- no
    manual chunking, and it still rides the same authenticated, encrypted Link.
  * Open-read (ALLOW_ALL): the point is to SHARE geo data with the mesh. The
    server identity still authenticates the server to clients (pinned dest hash).
    Client abuse is bounded by a per-link token bucket + a global concurrency cap,
    since the OSRM/Nominatim/Overpass backends are real compute.
  * Health-gated announces, same as rns-time: if the core backends are down we
    stop announcing (drop off the discoverable set) and mark responses degraded.
"""
import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import RNS

from . import backends, protocol

ANNOUNCE_INTERVAL = 900     # seconds
HEALTH_INTERVAL = 60
GLOBAL_CONCURRENCY = 8      # max simultaneous backend calls across all clients
PER_LINK_RPS = 2.0         # sustained requests/sec per link
PER_LINK_BURST = 6

_sem = threading.Semaphore(GLOBAL_CONCURRENCY)
_health = {"backends": {}, "ok": False, "checked": 0}
_dest_hash_hex = None

# ---- per-link token-bucket rate limiter -----------------------------------
_buckets = {}
_buckets_lock = threading.Lock()


def _allow(link_id):
    key = bytes(link_id) if link_id is not None else b"anon"
    now = time.time()
    with _buckets_lock:
        tokens, ts = _buckets.get(key, (PER_LINK_BURST, now))
        tokens = min(PER_LINK_BURST, tokens + (now - ts) * PER_LINK_RPS)
        if tokens >= 1.0:
            _buckets[key] = (tokens - 1.0, now)
            # opportunistic cleanup so the dict can't grow unbounded
            if len(_buckets) > 512:
                for k, (_, t) in list(_buckets.items()):
                    if now - t > 300:
                        _buckets.pop(k, None)
            return True
        _buckets[key] = (tokens, now)
        return False


# ---- op dispatch -----------------------------------------------------------
def _dispatch(req):
    op = req.get("op")
    if op not in protocol.OPS:
        return protocol.err("bad_op", req)
    try:
        if op == protocol.OP_REVERSE:
            r = backends.reverse(req["lat"], req["lon"])
            return protocol.ok({"res": r}, req) if r else protocol.err("not_found", req)
        if op == protocol.OP_FORWARD:
            r = backends.forward(req["q"], req.get("limit", 1))
            return protocol.ok({"res": r}, req)
        if op == protocol.OP_ROUTE:
            r = backends.route(req["frm"], req["to"], bool(req.get("geom", False)))
            return protocol.ok({"res": r}, req) if r else protocol.err("no_route", req)
        if op == protocol.OP_NEAREST:
            r = backends.nearest(req["lat"], req["lon"])
            return protocol.ok({"res": r}, req) if r else protocol.err("not_found", req)
        if op == protocol.OP_POI:
            r = backends.poi(req["lat"], req["lon"], req.get("radius", 1000),
                             req.get("cat"), req.get("limit", 20))
            return protocol.ok({"res": r}, req)
    except KeyError as e:
        return protocol.err("missing_field", req, str(e))
    except Exception as e:
        RNS.log(f"[rns-geo] backend error: {e}", RNS.LOG_DEBUG)
        return protocol.err("backend_error", req)
    return protocol.err("bad_op", req)


def on_request(path, data, request_id, link_id, remote_identity, requested_at):
    """RNS request-handler. Return umsgpack bytes (or None to send nothing)."""
    try:
        req = protocol.unpack(data)
    except Exception:
        return protocol.pack(protocol.err("bad_encoding"))
    if not isinstance(req, dict) or req.get("v") != protocol.VERSION:
        return protocol.pack(protocol.err("bad_version", req if isinstance(req, dict) else None))
    if not _allow(link_id):
        return protocol.pack(protocol.err("rate_limited", req))
    with _sem:
        resp = _dispatch(req)
    if not _health.get("ok"):
        resp["degraded"] = True
    return protocol.pack(resp)


# ---- health ----------------------------------------------------------------
def _refresh_health():
    global _health
    st = backends.health()
    _health = {"backends": st, "ok": bool(st.get("osrm") and st.get("nominatim")),
               "checked": time.time()}


def _health_loop():
    while True:
        try:
            _refresh_health()
        except Exception as e:
            RNS.log(f"[rns-geo] health probe failed: {e}", RNS.LOG_DEBUG)
        time.sleep(HEALTH_INTERVAL)


# ---- /healthz for Gatus ----------------------------------------------------
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") not in ("/healthz", ""):
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({
            "ok": _health.get("ok", False),
            "backends": _health.get("backends", {}),
            "dest_hash": _dest_hash_hex,
            "app": protocol.APP_NAME,
            "aspect": ".".join(protocol.ASPECTS),
        }).encode()
        self.send_response(200 if _health.get("ok") else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _start_healthz(port):
    srv = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    RNS.log(f"[rns-geo] healthz on :{port}")


def main():
    global _dest_hash_hex
    ap = argparse.ArgumentParser()
    ap.add_argument("--identity", default=os.path.expanduser("~/.rns_geo/identity"))
    ap.add_argument("--config", default=None)
    ap.add_argument("--healthz-port", type=int,
                    default=int(os.environ.get("HEALTHZ_PORT", "8213")))
    args = ap.parse_args()

    RNS.Reticulum(args.config)

    os.makedirs(os.path.dirname(args.identity), exist_ok=True)
    if os.path.isfile(args.identity):
        identity = RNS.Identity.from_file(args.identity)
    else:
        identity = RNS.Identity()
        identity.to_file(args.identity)

    dest = RNS.Destination(identity, RNS.Destination.IN, RNS.Destination.SINGLE,
                           protocol.APP_NAME, *protocol.ASPECTS)
    dest.register_request_handler(protocol.PATH, response_generator=on_request,
                                  allow=RNS.Destination.ALLOW_ALL)

    _dest_hash_hex = RNS.hexrep(dest.hash, delimit=False)
    RNS.log(f"[rns-geo] serving as {RNS.prettyhexrep(dest.hash)}")
    print(f"rns-geo destination: {_dest_hash_hex}", flush=True)

    _refresh_health()
    threading.Thread(target=_health_loop, daemon=True).start()
    _start_healthz(args.healthz_port)

    while True:
        if _health.get("ok"):
            dest.announce()
            RNS.log(f"[rns-geo] announced (backends {_health['backends']})")
        else:
            RNS.log(f"[rns-geo] NOT announcing -- backends unhealthy "
                    f"({_health['backends']})", RNS.LOG_WARNING)
        time.sleep(ANNOUNCE_INTERVAL)


if __name__ == "__main__":
    main()

"""Reference / CLI client for rns-geo.

  python3 -m rns_geo.client <dest_hash> rev  <lat> <lon>
  python3 -m rns_geo.client <dest_hash> fwd  "<query text>" [--limit N]
  python3 -m rns_geo.client <dest_hash> route <lat,lon> <lat,lon> [--geom]
  python3 -m rns_geo.client <dest_hash> near <lat> <lon>
  python3 -m rns_geo.client <dest_hash> poi  <lat> <lon> [--radius M] [--cat amenity=cafe] [--limit N]

Mirrors the rns-time client pattern: request a path, recall the identity, open a
Link, then use RNS's request/response over that link. LoRa needs patience, hence
the long default timeout.
"""
import argparse
import sys
import threading
import time

import RNS

from . import protocol


def _ll(s):
    lat, lon = s.split(",")
    return [float(lat), float(lon)]


def build_request(args):
    op = args.op
    if op == protocol.OP_REVERSE:
        return {"v": protocol.VERSION, "op": op, "lat": float(args.a[0]), "lon": float(args.a[1])}
    if op == protocol.OP_FORWARD:
        return {"v": protocol.VERSION, "op": op, "q": args.a[0], "limit": args.limit}
    if op == protocol.OP_ROUTE:
        return {"v": protocol.VERSION, "op": op, "frm": _ll(args.a[0]), "to": _ll(args.a[1]),
                "geom": args.geom}
    if op == protocol.OP_NEAREST:
        return {"v": protocol.VERSION, "op": op, "lat": float(args.a[0]), "lon": float(args.a[1])}
    if op == protocol.OP_POI:
        return {"v": protocol.VERSION, "op": op, "lat": float(args.a[0]), "lon": float(args.a[1]),
                "radius": args.radius, "cat": args.cat, "limit": args.limit}
    raise SystemExit(f"unknown op {op}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("server", help="rns-geo destination hash (64 hex)")
    ap.add_argument("op", choices=sorted(protocol.OPS))
    ap.add_argument("a", nargs="*", help="op args")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--radius", type=int, default=1000)
    ap.add_argument("--cat", default=None)
    ap.add_argument("--geom", action="store_true")
    ap.add_argument("--config", default=None, help="RNS config dir")
    ap.add_argument("--timeout", type=float, default=90.0)
    args = ap.parse_args()

    RNS.Reticulum(args.config)
    dest_hash = bytes.fromhex(args.server)

    if not RNS.Transport.has_path(dest_hash):
        RNS.Transport.request_path(dest_hash)
        deadline = time.time() + args.timeout
        while not RNS.Transport.has_path(dest_hash) and time.time() < deadline:
            time.sleep(0.5)
    if not RNS.Transport.has_path(dest_hash):
        print("no path to rns-geo (timed out)", file=sys.stderr)
        sys.exit(1)

    identity = RNS.Identity.recall(dest_hash)
    dest = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE,
                           protocol.APP_NAME, *protocol.ASPECTS)

    up = threading.Event()
    link = RNS.Link(dest, established_callback=lambda l: up.set())
    if not up.wait(args.timeout):
        print("link did not establish", file=sys.stderr)
        sys.exit(1)

    result = {}
    done = threading.Event()

    def on_response(receipt):
        try:
            result["resp"] = protocol.unpack(receipt.response)
        except Exception as e:
            result["error"] = f"bad response: {e}"
        done.set()

    def on_failed(receipt):
        result["error"] = "request failed / timed out"
        done.set()

    payload = protocol.pack(build_request(args))
    link.request(protocol.PATH, data=payload,
                 response_callback=on_response, failed_callback=on_failed,
                 timeout=args.timeout)

    if not done.wait(args.timeout + 5):
        print("no response", file=sys.stderr)
        sys.exit(2)
    link.teardown()

    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(2)

    import json
    print(json.dumps(result["resp"], indent=2, ensure_ascii=False))
    sys.exit(0 if result["resp"].get("ok") else 3)


if __name__ == "__main__":
    main()

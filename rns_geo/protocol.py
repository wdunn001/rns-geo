"""Wire protocol for rns-geo.

Compact umsgpack request/response over an RNS Link request-handler. Kept tiny so
answers survive a LoRa hop. Versioned like rns-time so the server can reject
mismatched clients.

NOTE (same gotcha as rns-time): the top-level `umsgpack` module is NOT reliably
importable just because RNS is installed -- RNS 1.4.2 vendors it under
RNS.vendor.umsgpack. The Dockerfile therefore `pip install`s `umsgpack`
explicitly; do not remove that.
"""
import umsgpack

APP_NAME = "rnsgeo"
ASPECTS = ("query",)
# Request-handler path registered on the destination. Clients call
# link.request(PATH, data=...). One path, many ops (op is a field in the body).
PATH = "q"
VERSION = 1

# Ops (short strings to save bytes on the wire)
OP_REVERSE = "rev"    # {lat, lon}                     -> {label, lat, lon}
OP_FORWARD = "fwd"    # {q, limit?}                    -> [{lat, lon, label}, ...]
OP_ROUTE   = "route"  # {frm:[lat,lon], to:[lat,lon], geom?} -> {dist_m, dur_s, poly?}
OP_NEAREST = "near"   # {lat, lon}                     -> {lat, lon, name?}
OP_POI     = "poi"    # {lat, lon, radius?, cat?, limit?} -> [{name, lat, lon, cat}, ...]
OPS = frozenset((OP_REVERSE, OP_FORWARD, OP_ROUTE, OP_NEAREST, OP_POI))


def pack(obj):
    return umsgpack.packb(obj)


def unpack(data):
    return umsgpack.unpackb(data)


def ok(payload, req=None):
    d = {"v": VERSION, "ok": True}
    d.update(payload)
    if req is not None and "id" in req:
        d["id"] = req["id"]
    return d


def err(code, req=None, msg=None):
    d = {"v": VERSION, "ok": False, "err": code}
    if msg:
        d["msg"] = msg
    if req is not None and isinstance(req, dict) and "id" in req:
        d["id"] = req["id"]
    return d

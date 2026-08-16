"""HTTP calls to the geo backends, with request-shaping to keep responses tiny
(LoRa-safe). Backend URLs come from env (OSRM_URL / NOMINATIM_URL / OVERPASS_URL)
and default to localhost -- point them at your own OSRM/Nominatim/Overpass.
stdlib urllib only, no extra deps.

Every function returns compact, already-trimmed data (strip polygons, address
detail, geometry unless explicitly asked). Callers pass through umsgpack as-is.
"""
import json
import os
import urllib.parse
import urllib.request

OSRM = os.environ.get("OSRM_URL", "http://127.0.0.1:5001")
NOMINATIM = os.environ.get("NOMINATIM_URL", "http://127.0.0.1:8092")
OVERPASS = os.environ.get("OVERPASS_URL", "http://127.0.0.1:8095/api/interpreter")
UA = "rns-geo/1 (+https://rns.quasarke.net)"
TIMEOUT = 8            # localhost backends are fast; keep short so the RNS handler never hangs long
OVERPASS_TIMEOUT = 15  # Overpass is the one slow backend


def _get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post_form(url, form, timeout):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def reverse(lat, lon):
    """coords -> a single place label (Nominatim /reverse)."""
    q = urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "jsonv2",
                                "addressdetails": 0, "zoom": 18})
    d = _get(f"{NOMINATIM}/reverse?{q}")
    if not d or not d.get("display_name"):
        return None
    return {"label": d["display_name"], "lat": float(d["lat"]), "lon": float(d["lon"])}


def forward(q, limit=1):
    """text -> top coord match(es) (Nominatim /search). limit capped at 5."""
    limit = max(1, min(int(limit), 5))
    qs = urllib.parse.urlencode({"q": q, "format": "jsonv2", "addressdetails": 0,
                                 "limit": limit})
    arr = _get(f"{NOMINATIM}/search?{qs}")
    return [{"lat": float(x["lat"]), "lon": float(x["lon"]), "label": x.get("display_name")}
            for x in (arr or [])]


def route(frm, to, geom=False):
    """A->B -> {dist_m, dur_s}; encoded polyline only if geom=True (opt-in, fatter)."""
    coords = f"{frm[1]},{frm[0]};{to[1]},{to[0]}"  # OSRM wants lon,lat
    params = {"overview": ("simplified" if geom else "false"),
              "steps": "false", "annotations": "false", "geometries": "polyline"}
    d = _get(f"{OSRM}/route/v1/driving/{coords}?{urllib.parse.urlencode(params)}")
    if d.get("code") != "Ok" or not d.get("routes"):
        return None
    r = d["routes"][0]
    out = {"dist_m": round(r["distance"]), "dur_s": round(r["duration"])}
    if geom and r.get("geometry"):
        out["poly"] = r["geometry"]  # encoded polyline (compact vs geojson)
    return out


def nearest(lat, lon):
    """snap a coord to the nearest routable point (OSRM /nearest)."""
    d = _get(f"{OSRM}/nearest/v1/driving/{lon},{lat}?number=1")
    if d.get("code") != "Ok" or not d.get("waypoints"):
        return None
    w = d["waypoints"][0]
    loc = w["location"]  # [lon, lat]
    return {"lat": loc[1], "lon": loc[0], "name": w.get("name") or None}


def poi(lat, lon, radius=1000, cat=None, limit=20):
    """named POIs within radius (Overpass). Strict caps: radius<=3km, limit<=30."""
    radius = max(50, min(int(radius), 3000))
    limit = max(1, min(int(limit), 30))
    filt = ""
    if cat:
        if "=" in str(cat):
            k, v = str(cat).split("=", 1)
            filt = f'["{k}"="{v}"]'
        else:
            filt = f'["amenity"="{cat}"]'
    ql = (f'[out:json][timeout:{OVERPASS_TIMEOUT}];'
          f'node(around:{radius},{lat},{lon}){filt}["name"];'
          f'out center {limit};')
    d = _post_form(OVERPASS, {"data": ql}, timeout=OVERPASS_TIMEOUT + 5)
    out = []
    for el in (d.get("elements") or [])[:limit]:
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        plat = el.get("lat")
        plon = el.get("lon")
        if plat is None:
            c = el.get("center") or {}
            plat, plon = c.get("lat"), c.get("lon")
        if plat is None or plon is None:
            continue
        cat_out = None
        for k in ("amenity", "shop", "tourism", "leisure"):
            if k in tags:
                cat_out = f"{k}={tags[k]}"
                break
        out.append({"name": name, "lat": plat, "lon": plon, "cat": cat_out})
    return out


def _reachable(url, timeout=4, data=None):
    """True if the URL answers 2xx. Does NOT parse the body -- Nominatim /status
    returns plain-text 'OK', not JSON, so json-parsing it would false-fail."""
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return 200 <= r.getcode() < 300


def health():
    """Reachability probe for each backend. Core = osrm + nominatim."""
    st = {}
    try:
        st["nominatim"] = _reachable(f"{NOMINATIM}/status", timeout=4)
    except Exception:
        st["nominatim"] = False
    try:
        # any 2xx from OSRM proves reachability (code may be NoSegment, fine)
        st["osrm"] = _reachable(f"{OSRM}/nearest/v1/driving/0,0?number=1", timeout=4)
    except Exception:
        st["osrm"] = False
    try:
        data = urllib.parse.urlencode({"data": "[out:json][timeout:5];out count;"}).encode()
        st["overpass"] = _reachable(OVERPASS, timeout=6, data=data)
    except Exception:
        st["overpass"] = False
    return st

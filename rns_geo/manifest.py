"""MeshAPI 0.1 manifest for rns-geo -- the single source of truth for this
service's ops. Served over RNS via the __manifest__ discovery op and rendered
into the NomadNet explorer page. Plain dict (conforms to MeshAPI 0.1; no meshapi
runtime dependency needed just to serve it). See github.com/wdunn001/meshapi.
"""
MANIFEST = {
    "meshapi": "0.1",
    "service": {
        "name": "rns-geo",
        "summary": "Geolocation data over Reticulum",
        "app": "rnsgeo",
        "aspect": "query",
        "path": "q",
        "dest": "2b20a86bfaf43c75810372dd73a53d1c",
        "encoding": "umsgpack",
        "source": "https://github.com/wdunn001/rns-geo",
    },
    "ops": [
        {"op": "rev", "summary": "Reverse geocode", "auth": "none",
         "request": {"lat": "float!", "lon": "float!"},
         "response": {"label": "str", "lat": "float", "lon": "float"}},
        {"op": "fwd", "summary": "Forward geocode", "auth": "none",
         "request": {"q": "str!", "limit": "int<=5"},
         "response": "[{lat,lon,label}]"},
        {"op": "route", "summary": "Route A to B", "auth": "none",
         "request": {"frm": "[lat,lon]!", "to": "[lat,lon]!", "geom": "bool"},
         "response": {"dist_m": "int", "dur_s": "int", "poly": "str?"}},
        {"op": "near", "summary": "Snap to nearest road", "auth": "none",
         "request": {"lat": "float!", "lon": "float!"},
         "response": {"lat": "float", "lon": "float", "name": "str?"}},
        {"op": "poi", "summary": "Nearby POIs", "auth": "none",
         "request": {"lat": "float!", "lon": "float!", "radius": "int<=3000",
                     "cat": "str?", "limit": "int<=30"},
         "response": "[{name,lat,lon,cat}]"},
    ],
}

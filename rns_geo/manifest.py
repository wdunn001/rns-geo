"""MeshAPI 0.1 manifest for rns-geo -- the single source of truth for this
service's ops. Served over RNS via the __manifest__ discovery op and rendered
into the NomadNet explorer page. Plain dict (conforms to MeshAPI 0.1; no meshapi
runtime dependency needed just to serve it). See github.com/wdunn001/meshapi.

Request fields are {type, desc} so the explorer can document each parameter.
"""
MANIFEST = {
    "meshapi": "0.1",
    "service": {
        "name": "rns-geo",
        "summary": "Geolocation data over Reticulum",
        "description": ("Geocoding, routing, snap-to-road and nearby-POI lookups over "
                        "an authenticated Reticulum Link. Responses are trimmed compact "
                        "enough for LoRa. Backed by OSRM, Nominatim and Overpass. Map "
                        "tiles are not served over the mesh (too heavy); this is data "
                        "only. Coordinates are decimal degrees (WGS84)."),
        "app": "rnsgeo",
        "aspect": "query",
        "path": "q",
        "dest": "2b20a86bfaf43c75810372dd73a53d1c",
        "encoding": "umsgpack",
        "source": "https://github.com/wdunn001/rns-geo",
    },
    "ops": [
        {"op": "rev", "summary": "Reverse geocode a coordinate to a place", "auth": "none",
         "request": {
             "lat": {"type": "float!", "desc": "latitude in decimal degrees"},
             "lon": {"type": "float!", "desc": "longitude in decimal degrees"}},
         "response": {"label": "str", "lat": "float", "lon": "float"}},
        {"op": "fwd", "summary": "Forward geocode: place text to coordinates", "auth": "none",
         "request": {
             "q": {"type": "str!", "desc": "free-text place/address query"},
             "limit": {"type": "int<=5", "desc": "max results (1-5, default 1)"}},
         "response": "[{lat,lon,label}]"},
        {"op": "route", "summary": "Driving route between two points", "auth": "none",
         "request": {
             "frm": {"type": "[lat,lon]!", "desc": "start point as lat,lon"},
             "to": {"type": "[lat,lon]!", "desc": "end point as lat,lon"},
             "geom": {"type": "bool", "desc": "include encoded polyline geometry (default false)"}},
         "response": {"dist_m": "int", "dur_s": "int", "poly": "str?"}},
        {"op": "near", "summary": "Snap a coordinate to the nearest road", "auth": "none",
         "request": {
             "lat": {"type": "float!", "desc": "latitude in decimal degrees"},
             "lon": {"type": "float!", "desc": "longitude in decimal degrees"}},
         "response": {"lat": "float", "lon": "float", "name": "str?"}},
        {"op": "poi", "summary": "Named points of interest near a coordinate", "auth": "none",
         "request": {
             "lat": {"type": "float!", "desc": "center latitude"},
             "lon": {"type": "float!", "desc": "center longitude"},
             "radius": {"type": "int<=3000", "desc": "search radius in metres (max 3000)"},
             "cat": {"type": "str?", "desc": "filter, e.g. amenity=cafe (optional)"},
             "limit": {"type": "int<=30", "desc": "max results (max 30)"}},
         "response": "[{name,lat,lon,cat}]"},
        {"op": "place", "summary": "Best place match with contact info (for a place card)",
         "auth": "none",
         "request": {"q": {"type": "str!", "desc": "place/POI/address text"}},
         "response": {"lat": "float", "lon": "float", "label": "str", "name": "str",
                      "cls": "str", "type": "str", "importance": "float",
                      "contact": "{phone?,website?,hours?}"}},
        {"op": "dir", "summary": "Turn-by-turn driving directions", "auth": "none",
         "request": {
             "q_from": {"type": "str?", "desc": "start place/address text (geocoded); or use frm"},
             "q_to": {"type": "str?", "desc": "destination place/address text (geocoded); or use to"},
             "frm": {"type": "[lat,lon]?", "desc": "start coordinate (instead of q_from)"},
             "to": {"type": "[lat,lon]?", "desc": "destination coordinate (instead of q_to)"}},
         "response": {"dist_m": "int", "dur_s": "int", "from_label": "str?",
                      "to_label": "str?", "steps": "[{text,dist_m}]"}},
    ],
}

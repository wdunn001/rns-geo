# rns-geo

A small **geolocation data service over [Reticulum](https://reticulum.network/)**.
It's a normal maps backend whose controller **listens on Reticulum instead of
HTTP**: it calls your own OSRM / Nominatim / Overpass instances over plain HTTP
and returns compact, trimmed results over an authenticated, encrypted RNS Link,
small enough to work over LoRa, I2P, or TCP.

Sibling project to [rns-time](https://github.com/wdunn001/rns-time) (time over
Reticulum); same shape, same deploy pattern.

## Ops
umsgpack request/response on the request path `q`, app `rnsgeo` / aspect `query`:

| op | request | response |
|----|---------|----------|
| `rev`   | `{lat, lon}` | `{label, lat, lon}`, reverse geocode |
| `fwd`   | `{q, limit?}` | `[{lat, lon, label}]`, forward geocode (limit ≤ 5) |
| `route` | `{frm:[lat,lon], to:[lat,lon], geom?}` | `{dist_m, dur_s, poly?}`, polyline only if `geom:true` |
| `near`  | `{lat, lon}` | `{lat, lon, name?}`, snap to nearest road |
| `poi`   | `{lat, lon, radius?, cat?, limit?}` | `[{name, lat, lon, cat}]`, radius ≤ 3 km, limit ≤ 30 |

Responses are shaped small on purpose: route geometry is opt-in, no polygons or
address detail, results capped. **Map tiles are deliberately not served**. They
are far too big for a mesh; a mesh map client caches tiles offline and uses these
data ops only.

## Design
- Uses RNS's **request-handler API** (`register_request_handler`), so RNS
  auto-delivers small answers as a packet and large ones as a Resource over the
  same Link. No manual chunking.
- **Open read** (`ALLOW_ALL`). The point is to share geo data. The server
  identity still authenticates the server to clients (pinned destination hash).
  Backend abuse is bounded by a **per-link token bucket** + a global concurrency
  cap.
- **Health-gated announces**: if a core backend (OSRM/Nominatim) is unreachable,
  the service stops announcing and flags responses `degraded:true`. A `/healthz`
  endpoint (default `:8213`) reports status for external monitoring.
- Own standalone RNS instance (`share_instance=No`, `enable_transport=No`);
  identity persisted so the destination hash is stable.

## Run
```bash
pip install rns umsgpack
# point OSRM_URL / NOMINATIM_URL / OVERPASS_URL at your backends, then:
python3 -m rns_geo.server --identity ./data/identity --config ./config
# note the "rns-geo destination: <hash>" line it prints
```
Or with Docker (see `docker-compose.example.yml` and `config/rns-config.example`):
```bash
docker compose -f docker-compose.example.yml up -d --build
docker logs rns-geo --tail 20
curl -s localhost:8213/healthz
```
It needs a Reticulum instance to ride, either a local `rnsd` (recommended;
connect via its loopback `TCPServerInterface`) or a public transport node. See
`config/rns-config.example`.

## Client
```bash
python3 -m rns_geo.client <dest_hash> rev   36.0 -83.9
python3 -m rns_geo.client <dest_hash> fwd   "knoxville tn" --limit 3
python3 -m rns_geo.client <dest_hash> route 36.0,-83.9 35.96,-83.92 --geom
python3 -m rns_geo.client <dest_hash> near  36.0 -83.9
python3 -m rns_geo.client <dest_hash> poi   36.0 -83.9 --radius 800 --cat amenity=cafe
```

## Backends
Bring your own, any standard deployment works:
- **OSRM**, routing (`/route`, `/nearest`)
- **Nominatim**, forward/reverse geocoding (`/search`, `/reverse`)
- **Overpass**, POI queries (`/api/interpreter`, Overpass QL)

## License
MIT. See `LICENSE`.

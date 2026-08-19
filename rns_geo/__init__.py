"""rns-geo, a compact geolocation data service over Reticulum.

Exposes the quasarke geo backends (OSRM routing, Nominatim geocoding, Overpass
POI) as small request/response ops over an authenticated RNS Link, usable over
TCP / I2P / LoRa. Modeled on rns-time; upstream also at
github.com/wdunn001/rns-geo (keep in lockstep with this vendored copy).
"""
__version__ = "1"

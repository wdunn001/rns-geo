FROM python:3.12-slim
# rns-geo: Reticulum geolocation data service. Backends are reached over plain
# HTTP via stdlib urllib (no requests dep). umsgpack is installed EXPLICITLY.
# Despite protocol.py's "bundled with RNS" lineage, the top-level `umsgpack`
# module is not reliably importable from an RNS install (RNS vendors it under
# RNS.vendor.umsgpack). Same gotcha rns-time hit.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir rns umsgpack
COPY rns_geo /app/rns_geo
WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "-m", "rns_geo.server"]
CMD ["--identity", "/data/identity", "--config", "/config/rns"]

# osmium-tool for the pack pipeline (ADR-036): turns normalize_osm.py's XML into the sorted PBF Planetiler reads,
# with the OSM data timestamp in the file header. No maintained official osmium image exists.
# Built by pipeline/lib.sh (ensure_osmium_image) as snowbuddy-maps/osmium:1.18.0. It only reads and writes local
# files, so it needs no CA certificates or network at run time.
FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
RUN apt-get update \
 && apt-get install -y --no-install-recommends osmium-tool=1.18.0-1 \
 && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["osmium"]

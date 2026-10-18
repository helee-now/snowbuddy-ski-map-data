#!/usr/bin/env bash
# Builds the ski file of a resort map pack on its own: <key>-ski.pmtiles, with runs, run areas, lifts, lift stations,
# the ski-area outline and 20 m contours (vector tiles, z9-14), made from OpenStreetMap data and an elevation model.
# These are the steps build-pack.sh runs for the ski file (pipeline/ski.sh); this script is how the public ski map
# data repository rebuilds its files.
#
# Usage:
#   bash pipeline/build-ski.sh <slug>|all [options]
# Options:
#   --osm-date=recorded          (default) the OSM data the published file was built from: the resort's
#                                osm_timestamp in resorts.json, else its record in packs/<key>/pack.json
#   --osm-date=YYYY-MM-DDTHH:MM:SSZ   the OSM data as it was at that time
#   --osm-date=current           the current OSM data (or the cached answer)
#   --osm-file=PATH              use this saved Overpass answer (OSM XML) for the resort
#   --refresh-osm                ask Overpass again even when the answer to this query is cached
# Environment: SKI_OUT_DIR (default out/ next to pipeline/), OVERPASS_URL (default https://overpass-api.de/api/interpreter).
# Writes <out>/<key>-ski.pmtiles and <out>/<key>-coverage.json, then compares the file with the recorded SHA-256
# (resorts.json or packs/<key>/pack.json): with the recorded OSM data and elevation sources unchanged it is the same file.
# Needs bash, Docker (images pinned in pipeline/lib.sh) and python3; runs `pmtiles verify` when the pmtiles CLI is
# installed. Downloads: one Overpass request per resort (cached in .cache/), and the elevation blocks over HTTPS.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
source "$(dirname "${BASH_SOURCE[0]}")/ski.sh"

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}" >&2; exit 2; }

TARGET=""; OSM_FILE=""; REFRESH_OSM=0; OSM_DATE_ARG="recorded"
while [ $# -gt 0 ]; do
  case "$1" in
    --osm-file=*) OSM_FILE="$(python3 -I -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "${1#*=}")" ;;
    --refresh-osm) REFRESH_OSM=1 ;;
    --osm-date=*) OSM_DATE_ARG="${1#*=}" ;;
    -h|--help) usage ;;
    -*) die "unknown option $1" ;;
    *) [ -z "$TARGET" ] || die "give one slug, or all"; TARGET="$1" ;;
  esac
  shift
done
[ -n "$TARGET" ] || usage
check_osm_date_arg
if [ -n "$OSM_FILE" ] && [ "$TARGET" = all ]; then die "--osm-file is for one resort at a time"; fi

command -v docker >/dev/null || die "Docker is required"
docker info >/dev/null 2>&1 || die "Docker is not running"
OUT_DIR="${SKI_OUT_DIR:-$MAPS_ROOT/out}"
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
CACHE="$MAPS_ROOT/.cache"
mkdir -p "$CACHE"

build_one() {
  local SLUG KEY VERSION BOX SKI_AREA ELEV ELEV_RES ELEV_PROJECT CONTOUR_SMOOTH_M OSM_CREDIT_HTML TERRAIN_CREDIT_HTML assigns
  assigns="$(python3 -I "$PIPE/packlib.py" resort "$MAPS_ROOT/resorts.json" "$1")" || die "resorts.json has no usable entry for '$1'"
  eval "$assigns"
  check_box "$BOX"
  local wk="$CACHE/$SLUG/$KEY" t0=$SECONDS
  mkdir -p "$wk"
  log "=== $KEY-ski.pmtiles: box $BOX, elevation $ELEV"

  local OSM_DATE OSM_RAW OSM_BASE OSM_QBOX OSM_ANSWER_BOX DEM
  build_ski "$wk"
  if command -v pmtiles >/dev/null; then
    pmtiles verify "$wk/ski.pmtiles" > "$wk/verify-ski.log" 2>&1 || { cat "$wk/verify-ski.log" >&2; die "pmtiles verify failed"; }
  fi

  local out="$OUT_DIR/$KEY-ski.pmtiles" sha recorded
  cp "$wk/ski.pmtiles" "$out.part" && mv "$out.part" "$out"
  cp "$wk/coverage.json" "$OUT_DIR/$KEY-coverage.json"
  sha="$(python3 -I -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$out")"
  log "  $out: $(wc -c < "$out" | tr -d ' ') bytes, OSM data of $OSM_BASE, SHA-256 $sha"
  if recorded="$(python3 -I "$PIPE/packlib.py" recorded ski_sha256 "$MAPS_ROOT/resorts.json" "$SLUG" "$MAPS_ROOT/packs/$KEY/pack.json")"; then
    if [ "$sha" = "$recorded" ]; then
      log "  identical to the published $KEY-ski.pmtiles"
    else
      log "  differs from the published $KEY-ski.pmtiles ($recorded): expected with other OSM data, or when an elevation source has been updated"
    fi
  fi
  log "=== $KEY built in $((SECONDS - t0)) s"
}

verify_profile
if [ "$TARGET" = all ]; then
  while IFS= read -r slug; do build_one "$slug"; done < <(python3 -I "$PIPE/packlib.py" slugs "$MAPS_ROOT/resorts.json")
else
  build_one "$TARGET"
fi

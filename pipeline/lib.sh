# Shared settings for the pack pipeline scripts (sourced, not run). Bash only: the research's runaway planet
# extract came from zsh word splitting an unquoted variable into an empty --bbox.

# Images pinned by digest (ADR-036). Pulled once, then used offline.
GDAL_IMAGE="ghcr.io/osgeo/gdal:ubuntu-small-3.13.3@sha256:64250faf833c06d4b21afce4c27190039ba7ab58d70f0eebc87cf77d929c0b40"
PLANETILER_IMAGE="ghcr.io/onthegomap/planetiler:0.10.2@sha256:cf32202dbc001a9ab4bc11534b642b13de3798179817da8558e567a3d13dd403"
# osmium 1.18.0 from Debian trixie, built locally from pipeline/docker/osmium (base image pinned by digest there).
OSMIUM_IMAGE="snowbuddy-maps/osmium:1.18.0"
OSMIUM_VERSION="1.18.0"

# A plain User-Agent for every request the pipeline makes. Never put an e-mail address or other personal data in it.
MAPS_USER_AGENT="SnowBuddy-maps/0.1"

MAPS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PIPE="$MAPS_ROOT/pipeline"

die() { echo "error: $*" >&2; exit 1; }
log() { echo "[$(date +%H:%M:%S)] $*" >&2; }

# Path inside the containers (packages/maps is mounted at /w). Refuses paths outside packages/maps.
in_root() {
  local abs
  abs="$(python3 -I -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1")"
  case "$abs" in
    "$MAPS_ROOT"/*) echo "/w/${abs#"$MAPS_ROOT"/}" ;;
    *) die "$1 is outside $MAPS_ROOT (only packages/maps is mounted into the containers)" ;;
  esac
}

gd() {
  docker run --rm -u "$(id -u):$(id -g)" -v "$MAPS_ROOT:/w" -w /w \
    -e GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR -e CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif,.vrt \
    -e GDAL_HTTP_MULTIRANGE=YES -e GDAL_HTTP_MERGE_CONSECUTIVE_RANGES=YES -e VSI_CACHE=TRUE \
    -e GDAL_HTTP_USERAGENT="$MAPS_USER_AGENT" -e GDAL_HTTP_MAX_RETRY=4 -e GDAL_HTTP_RETRY_DELAY=5 \
    "$GDAL_IMAGE" "$@"
}

osmium_run() {
  docker run --rm -u "$(id -u):$(id -g)" -v "$MAPS_ROOT:/w" -w /w "$OSMIUM_IMAGE" "$@"
}

ensure_osmium_image() {
  if ! docker image inspect "$OSMIUM_IMAGE" >/dev/null 2>&1; then
    log "building $OSMIUM_IMAGE from pipeline/docker/osmium"
    docker build -q -t "$OSMIUM_IMAGE" "$PIPE/docker/osmium" >/dev/null
  fi
  local v
  v="$(docker run --rm "$OSMIUM_IMAGE" --version | head -1)"
  [ "$v" = "osmium version $OSMIUM_VERSION" ] || die "$OSMIUM_IMAGE reports '$v', expected osmium $OSMIUM_VERSION"
}

# forget_stale_cuts <work dir> <W,S,E,N>: the cached base map, elevation window and contours of a pack are cut to its
# box, so they are dropped when the box is not the one recorded in <work dir>/box.txt (a cache without that record
# is cut again once). A box only changes under the same key while the key has never shipped.
forget_stale_cuts() {
  local wk="$1" box="$2" stamp="$1/box.txt"
  [ "$(cat "$stamp" 2>/dev/null)" = "$box" ] && return 0
  if [ -e "$wk/base.pmtiles" ] || compgen -G "$wk/dem-*.tif" >/dev/null || compgen -G "$wk/contours-*.gpkg" >/dev/null; then
    log "the cache in $wk was cut to another box (or has no box record); cutting the base map, elevation and contours again"
  fi
  rm -f "$wk/base.pmtiles" "$wk/base.json" "$wk"/dem-*.tif "$wk"/dem-*.inputs.txt "$wk"/contours-*.gpkg
  mkdir -p "$wk"
  printf '%s\n' "$box" > "$stamp"
}

# check_box W,S,E,N [max square degrees, default 0.1]. The pack box itself always uses the default; the windows
# around it (elevation, Overpass: the box plus a margin) pass a larger limit.
check_box() {
  python3 -I "$PIPE/packlib.py" check-box "$1" ${2:+"$2"} || die "box guard refused '$1'"
}

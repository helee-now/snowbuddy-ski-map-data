#!/usr/bin/env bash
# Crops one elevation source to a lon/lat window into a local GeoTIFF. GDAL reads only the needed blocks of the
# cloud-optimised GeoTIFFs over HTTPS (/vsicurl/); no account or key.
#
# Usage: fetch-dem.sh <source> <out.tif> <W,S,E,N> [--box=W,S,E,N] [--project=NAME] [--list]
#   --list writes <out>.inputs.txt, prints the URLs it would read and stops (no elevation data is downloaded)
# The 30 m and 10 m sources keep their own grid: same CRS, same resolution, -tap alignment, nearest neighbour, so no
# resampling happens here.
#   mrdem30  NRCan MRDEM-30 DTM (bare earth, 30 m, EPSG:3979, CGVD2013 metres), one COG for all of Canada
#   3dep13   USGS 3DEP 1/3 arc-second (about 10 m, lidar-based, EPSG:4269, NAVD88 metres), 1-degree tiles named by
#            their NW corner
#   cop30    Copernicus GLO-30 DSM (surface, trees included), 1-degree tiles; fallback outside Canada and the US.
#            Add its verified credit to resorts.json before using it.
# The 1 m lidar sources are averaged onto the Web Mercator grid of 512 px zoom-14 tiles (4.777 m: every hillshade zoom
# then averages whole pixels), reading the COGs' overviews when shrinking:
#   3dep1    USGS 3DEP 1 m DEM (lidar, bare earth, NAVD88 metres, UTM): the 10 km tiles of one 3DEP project
#            (--project, pinned per resort in resorts.json), found with The National Map's product API and mosaicked
#            with a VRT
#   hrdem1   NRCan HRDEM mosaic 1 m DTM (lidar, bare earth, CGVD2013 metres, EPSG:3979), found with NRCan's STAC API.
#            No resort uses it: on 2026-10-17 it held only the valley floor of Whistler Blackcomb's window (7.3%) and
#            0.6% of Big White's, none of either ski area. Add its verified credit to resorts.json before using it.
#   The lidar must hold at least MIN_LIDAR_BOX_PCT of the box (--box, the pack's box; default the window), counted by
#   pixel centres. Holes in the window are filled from the coarser model of the same country, on the same vertical
#   datum and in the same units (3dep1 from 3dep13, hrdem1 from mrdem30), resampled onto the grid with a cubic spline.
#   <out>.coverage.json records the shares.
# <out.tif> must be under packages/maps. Writes <out>.inputs.txt with the URLs read (the fill's too, when used).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SRC="${1:?source}"; OUT="${2:?out.tif}"; BOX="${3:?W,S,E,N}"
shift 3
PACK_BOX="$BOX"; PROJECT=""; LIST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --box=*) PACK_BOX="${1#*=}" ;;
    --project=*) PROJECT="${1#*=}" ;;
    --list) LIST=1 ;;
    *) die "unknown option $1" ;;
  esac
  shift
done
check_box "$BOX" 0.2
check_box "$PACK_BOX" 0.2
IFS=, read -r W S E N <<< "$BOX"
mkdir -p "$(dirname "$OUT")"
INPUTS="${OUT%.tif}.inputs.txt"
COVERAGE="${OUT%.tif}.coverage.json"
trap 'rm -f "$INPUTS.part" "${OUT%.tif}.catalogue.json"' EXIT
DEM_GRID_M=4.777314267823516   # 2 x 20037508.342789244 m / 2^14 tiles / 512 px
MIN_LIDAR_BOX_PCT=95
TNM_API="${TNM_API:-https://tnmaccess.nationalmap.gov/api/v1/products}"
STAC_API="${STAC_API:-https://datacube.services.geo.ca/stac/api}"
rm -f "$COVERAGE"

# static_inputs <source>: the URLs of a 30 m or 10 m source over the window.
static_inputs() {
  python3 -I - "$1" "$W" "$S" "$E" "$N" <<'EOF'
import math, sys
src, w, s, e, n = sys.argv[1], *map(float, sys.argv[2:])
if src == 'mrdem30':
    print('https://canelevation-dem.s3.ca-central-1.amazonaws.com/mrdem-30/mrdem-30-dtm.tif')
elif src == '3dep13':
    # Tile nLLwMMM covers latitudes LL-1..LL and longitudes -MMM..-(MMM-1).
    for lat in range(math.floor(s) + 1, math.ceil(n) + 1):
        for lon in range(math.floor(-e) + 1, math.ceil(-w) + 1):
            t = f'n{lat:02d}w{lon:03d}'
            print(f'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/{t}/USGS_13_{t}.tif')
elif src == 'cop30':
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            t = 'Copernicus_DSM_COG_10_%s%02d_00_%s%03d_00_DEM' % ('N' if lat >= 0 else 'S', abs(lat), 'E' if lon >= 0 else 'W', abs(lon))
            print(f'https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif')
else:
    sys.exit(f'unknown elevation source {src}')
EOF
}

# fetch_json <out> <curl args...>: one API answer, with a plain User-Agent, retried on failure.
fetch_json() {
  local out="$1" attempt
  shift
  for attempt in 1 2 3 4; do
    if curl -sSf -A "$MAPS_USER_AGENT" --max-time 120 -o "$out" "$@"; then return 0; fi
    [ "$attempt" -lt 4 ] || break
    log "elevation API request $attempt failed; trying again in $((attempt * 15)) s"
    sleep $((attempt * 15))
  done
  return 1
}

# lidar_inputs: the 1 m tiles over the window, from the source's catalogue (packlib.py reads the answer).
lidar_inputs() {
  local answer="${OUT%.tif}.catalogue.json"
  case "$SRC" in
    3dep1)
      [ -n "$PROJECT" ] || die "3dep1 needs --project (the 3DEP project, pinned per resort in resorts.json)"
      fetch_json "$answer" -G "$TNM_API" --data-urlencode "datasets=Digital Elevation Model (DEM) 1 meter" \
        --data-urlencode "bbox=$W,$S,$E,$N" --data-urlencode "max=1000" --data-urlencode "outputFormat=JSON" \
        || die "The National Map's product API did not answer"
      # A project near a UTM zone boundary lists tiles in both zones; the window centre's zone is kept (gdalbuildvrt
      # mosaics one projection and would skip the rest).
      python3 -I "$PIPE/packlib.py" tnm-tiles "$answer" "$PROJECT" \
        "$(python3 -I -c 'import sys; print((float(sys.argv[1]) + float(sys.argv[2])) / 2)' "$W" "$E")" ;;
    hrdem1)
      fetch_json "$answer" -G "$STAC_API/collections/hrdem-mosaic-1m/items" --data-urlencode "bbox=$W,$S,$E,$N" \
        --data-urlencode "limit=100" || die "NRCan's STAC API did not answer"
      python3 -I "$PIPE/packlib.py" stac-assets "$answer" dtm ;;
  esac
  rm -f "$answer"
}

# warp_lidar <fill source>: the 1 m tiles averaged onto the grid, the coverage rule, and the fill.
warp_lidar() {
  local fill="$1" vrt="${OUT%.tif}.vrt" fine="${OUT%.tif}.lidar.tif" coarse="${OUT%.tif}.fill.tif" nd cov
  local -a sources=() fills=() te
  while IFS= read -r url; do sources+=("/vsicurl/$url"); done < "$INPUTS"
  nd="$(gd gdalinfo -json "${sources[0]}" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["bands"][0]["noDataValue"])')"
  gd gdalbuildvrt -q -overwrite -srcnodata "$nd" -vrtnodata "$nd" "$(in_root "$vrt")" "${sources[@]}"
  gd gdalwarp -q -overwrite -t_srs EPSG:3857 -tr "$DEM_GRID_M" "$DEM_GRID_M" -tap -te_srs EPSG:4326 -te "$W" "$S" "$E" "$N" \
    -r average -srcnodata "$nd" -dstnodata -32768 -ot Float32 -co COMPRESS=DEFLATE -co PREDICTOR=3 -co TILED=YES \
    -wm 1024 -multi -wo NUM_THREADS=ALL_CPUS "$(in_root "$vrt")" "$(in_root "$fine")"
  rm -f "$vrt"
  cov="$(gd python3 -I /w/pipeline/dem.py coverage "$(in_root "$fine")" "$PACK_BOX")"
  log "elevation $SRC: the lidar holds $(python3 -I -c 'import json,sys; c=json.loads(sys.argv[1]); print("%s%% of the box, %s%% of the window (%s pixels missing)" % (c["box_pct"], c["window_pct"], c.get("window_missing_px")))' "$cov")"
  # The fill is decided on the exact count of missing pixels, not the rounded share (packlib.py lidar-plan).
  local plan filled=0 filled_px=0 status=0
  plan="$(python3 -I "$PIPE/packlib.py" lidar-plan "$cov" "$MIN_LIDAR_BOX_PCT")" || status=$?
  if [ "$status" -ne 0 ]; then
    rm -f "$fine"
    [ "$status" -ne 1 ] && die "the coverage of $SRC could not be read: $cov"
    die "$SRC holds less than $MIN_LIDAR_BOX_PCT% of the box $PACK_BOX; keep the resort on a coarser source"
  fi
  if [ "$plan" = fill ]; then
    # The coarse model onto exactly the same grid, then the lidar's holes filled from it.
    while IFS= read -r url; do fills+=("/vsicurl/$url"); done < <(static_inputs "$fill")
    read -r -a te <<< "$(gd gdalinfo -json "$(in_root "$fine")" | python3 -I -c 'import json,sys; g=json.load(sys.stdin); t=g["geoTransform"]; nx,ny=g["size"]; print(f"{t[0]!r} {t[3]+ny*t[5]!r} {t[0]+nx*t[1]!r} {t[3]!r}")')"
    gd gdalwarp -q -overwrite -t_srs EPSG:3857 -tr "$DEM_GRID_M" "$DEM_GRID_M" -te "${te[@]}" -r cubicspline \
      -dstnodata -32768 -ot Float32 -co COMPRESS=DEFLATE -co PREDICTOR=3 -co TILED=YES "${fills[@]}" "$(in_root "$coarse")"
    read -r filled filled_px <<< "$(gd python3 -I /w/pipeline/dem.py fill "$(in_root "$fine")" "$(in_root "$coarse")" "$(in_root "$OUT")" \
      | python3 -I -c 'import json,sys; d=json.load(sys.stdin); print(d["filled_pct"], d["filled_px"])')"
    rm -f "$fine" "$coarse"
    printf '%s\n' "${fills[@]#/vsicurl/}" >> "$INPUTS"
    log "elevation $SRC: filled $filled_px pixels ($filled% of the window) from $fill"
  else
    mv "$fine" "$OUT"
    fill=""
  fi
  python3 -I - "$COVERAGE" "$SRC" "$PROJECT" "$DEM_GRID_M" "$cov" "$fill" "$filled" "$PACK_BOX" "$MIN_LIDAR_BOX_PCT" <<'EOF'
import json, sys
out, src, project, grid, cov, fill, filled, box, minimum = sys.argv[1:]
c = json.loads(cov)
doc = {'source': src, 'project': project or None, 'grid': f'EPSG:3857, {float(grid):.6f} m', 'box': [float(v) for v in box.split(',')],
       'lidar_box_pct': c['box_pct'], 'lidar_window_pct': c['window_pct'], 'min_lidar_box_pct': float(minimum),
       'fill_source': fill or None, 'filled_window_pct': float(filled)}
with open(out, 'w', encoding='utf-8') as f:
    json.dump(doc, f, indent=1)
    f.write('\n')
EOF
}

if [ "$LIST" = 1 ]; then
  case "$SRC" in
    3dep1|hrdem1) lidar_inputs > "$INPUTS.part" ;;
    *) static_inputs "$SRC" > "$INPUTS.part" ;;
  esac
  mv "$INPUTS.part" "$INPUTS"
  cat "$INPUTS"
  exit 0
fi
case "$SRC" in
  mrdem30|3dep13|cop30)
    static_inputs "$SRC" > "$INPUTS"
    TSRS=""; TR=""; RESAMPLE="near"
    case "$SRC" in
      mrdem30) TSRS=EPSG:3979 ;;
      3dep13) TSRS=EPSG:4269 ;;
      # GLO-30 tiles north of 50 N are 1.5" wide, south of it 1": bring all to 1" with bilinear (nearest would
      # duplicate columns and stripe the hillshade).
      cop30) TSRS=EPSG:4326; TR="0.000277777777778 0.000277777777778"; RESAMPLE=bilinear ;;
    esac
    SOURCES=()
    while IFS= read -r url; do SOURCES+=("/vsicurl/$url"); done < "$INPUTS"
    [ "${#SOURCES[@]}" -gt 0 ] || die "no input tiles for $SRC over $BOX"
    if [ -z "$TR" ]; then
      # Keep the source's own pixel size (first input), so the crop keeps the original pixels.
      TR="$(gd gdalinfo -json "${SOURCES[0]}" | python3 -I -c 'import json,sys; g=json.load(sys.stdin)["geoTransform"]; print(f"{abs(g[1]):.15g} {abs(g[5]):.15g}")')"
    fi
    # shellcheck disable=SC2086
    gd gdalwarp -q -overwrite -t_srs "$TSRS" -tr $TR -tap -te_srs EPSG:4326 -te "$W" "$S" "$E" "$N" -r "$RESAMPLE" \
      -co COMPRESS=DEFLATE -co PREDICTOR=3 -co TILED=YES -ot Float32 -dstnodata -32768 "${SOURCES[@]}" "$(in_root "$OUT")" ;;
  3dep1|hrdem1)
    lidar_inputs > "$INPUTS.part"
    mv "$INPUTS.part" "$INPUTS"
    [ -s "$INPUTS" ] || die "no $SRC tiles${PROJECT:+ of $PROJECT} over $BOX"
    case "$SRC" in
      3dep1) warp_lidar 3dep13 ;;
      hrdem1) warp_lidar mrdem30 ;;
    esac ;;
  *) die "unknown elevation source $SRC" ;;
esac
gd gdalinfo -stats "$(in_root "$OUT")" | grep -E "Size is|Pixel Size|STATISTICS_(MINIMUM|MAXIMUM|VALID_PERCENT)" | tr -s ' ' >&2
rm -f "$OUT.aux.xml"
VALID="$(gd gdalinfo -stats -json "$(in_root "$OUT")" | python3 -I -c 'import json,sys; b=json.load(sys.stdin)["bands"][0]; print(b.get("metadata",{}).get("",{}).get("STATISTICS_VALID_PERCENT","0"))')"
rm -f "$OUT.aux.xml"
python3 -I -c 'import sys; v=float(sys.argv[1]); sys.exit(0 if v >= 99.0 else 1)' "$VALID" \
  || die "$OUT is only $VALID% valid; the elevation source does not cover the box"
log "elevation $SRC: $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes, $VALID% valid)"

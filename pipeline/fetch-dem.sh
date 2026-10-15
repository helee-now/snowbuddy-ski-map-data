#!/usr/bin/env bash
# Crops one elevation source to a lon/lat box into a local GeoTIFF on the source's own grid: same CRS, same
# resolution, -tap alignment, nearest neighbour, so no resampling happens here. GDAL reads only the needed blocks of
# the cloud-optimised GeoTIFFs over HTTPS (/vsicurl/); no account or key.
#
# Usage: fetch-dem.sh <source> <out.tif> <W,S,E,N>
#   mrdem30  NRCan MRDEM-30 DTM (bare earth, 30 m, EPSG:3979), one COG for all of Canada
#   3dep13   USGS 3DEP 1/3 arc-second (about 10 m, lidar-based, EPSG:4269), 1-degree tiles named by their NW corner
#   cop30    Copernicus GLO-30 DSM (surface, trees included), 1-degree tiles; fallback outside Canada and the US.
#            Add its verified credit to resorts.json before using it.
# <out.tif> must be under packages/maps. Writes <out>.inputs.txt with the URLs read.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SRC="${1:?source}"; OUT="${2:?out.tif}"; BOX="${3:?W,S,E,N}"
check_box "$BOX" 0.2
IFS=, read -r W S E N <<< "$BOX"
mkdir -p "$(dirname "$OUT")"
INPUTS="${OUT%.tif}.inputs.txt"
TSRS=""; TR=""; RESAMPLE="near"
python3 -I - "$SRC" "$W" "$S" "$E" "$N" > "$INPUTS" <<'EOF'
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
  -co COMPRESS=DEFLATE -co PREDICTOR=3 -co TILED=YES -ot Float32 -dstnodata -32768 "${SOURCES[@]}" "$(in_root "$OUT")"
gd gdalinfo -stats "$(in_root "$OUT")" | grep -E "Size is|Pixel Size|STATISTICS_(MINIMUM|MAXIMUM|VALID_PERCENT)" | tr -s ' ' >&2
rm -f "$OUT.aux.xml"
VALID="$(gd gdalinfo -stats -json "$(in_root "$OUT")" | python3 -I -c 'import json,sys; b=json.load(sys.stdin)["bands"][0]; print(b.get("metadata",{}).get("",{}).get("STATISTICS_VALID_PERCENT","0"))')"
rm -f "$OUT.aux.xml"
python3 -I -c 'import sys; v=float(sys.argv[1]); sys.exit(0 if v >= 99.0 else 1)' "$VALID" \
  || die "$OUT is only $VALID% valid; the elevation source does not cover the box"
log "elevation $SRC: $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes, $VALID% valid)"

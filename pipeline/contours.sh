#!/usr/bin/env bash
# Contour lines from a local elevation GeoTIFF: resample to a 10 m Web Mercator grid with a cubic spline (smooths
# the 30 m staircase), run gdal_contour at the interval, and write EPSG:4326 lines with an integer `ele` (metres)
# into a GeoPackage for Planetiler. Index lines (every 100 m) are marked by the Planetiler profile.
#
# Usage: contours.sh <dem.tif> <out.gpkg> <W,S,E,N> [interval_m=20] [grid_m=10] [margin_deg=0.005]
# Both paths must be under packages/maps.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
DEM="${1:?dem.tif}"; OUT="${2:?out.gpkg}"; BOX="${3:?W,S,E,N}"; INTERVAL="${4:-20}"; GRID="${5:-10}"; MARGIN="${6:-0.005}"
check_box "$BOX"
read -r W2 S2 E2 N2 RES <<< "$(python3 -I - "$BOX" "$MARGIN" "$GRID" <<'EOF'
import math, sys
w, s, e, n = map(float, sys.argv[1].split(','))
m, g = float(sys.argv[2]), float(sys.argv[3])
# Web Mercator metres per true metre grow with 1/cos(latitude).
print(w - m, s - m, e + m, n + m, g / math.cos(math.radians((s + n) / 2)))
EOF
)"
BASE="${OUT%.gpkg}"
rm -f "$BASE-grid.tif" "$BASE-3857.gpkg" "$OUT"
gd gdalwarp -q -overwrite -t_srs EPSG:3857 -tr "$RES" "$RES" -r cubicspline -te_srs EPSG:4326 -te "$W2" "$S2" "$E2" "$N2" \
  -srcnodata -32768 -dstnodata -32768 -co COMPRESS=DEFLATE -co PREDICTOR=3 "$(in_root "$DEM")" "$(in_root "$BASE-grid.tif")"
gd gdal_contour -q -a ele -i "$INTERVAL" -snodata -32768 -f GPKG -nln contours "$(in_root "$BASE-grid.tif")" "$(in_root "$BASE-3857.gpkg")"
gd ogr2ogr -f GPKG -t_srs EPSG:4326 -nln contours -sql "SELECT CAST(ele AS INTEGER) AS ele, geom FROM contours" \
  "$(in_root "$OUT")" "$(in_root "$BASE-3857.gpkg")"
gd ogrinfo -so -al "$(in_root "$OUT")" | grep -E "Feature Count|Extent" >&2
rm -f "$BASE-grid.tif" "$BASE-3857.gpkg"
log "contours every ${INTERVAL} m: $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"

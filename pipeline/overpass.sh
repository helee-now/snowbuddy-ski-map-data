#!/usr/bin/env bash
# Fetches one resort's ski features from Overpass as OSM XML: runs (piste:type, snow parks, halfpipes), aerialways,
# ski-area polygons (landuse=winter_sports) and piste route relations, with every node they use. `out body` leaves
# out OSM user names and changesets; the answer's <meta osm_base> records the data timestamp.
#
# Usage: overpass.sh <out.osm> <W,S,E,N> [<osm_base ISO 8601>]
#        overpass.sh --print-query <W,S,E,N> [<osm_base ISO 8601>]    prints the query; sends nothing
#   The third argument rebuilds the data as it was at that time ([date:"..."]), for an exact rebuild of a pack.
#   Next to a saved answer goes <out.osm>.query, the exact query that made it (box, date and selection): ski.sh
#   reuses a cached answer only when that record is the query it would send now.
# One request per call; on 429, 502, 503, 504 or a timeout remark it waits (Retry-After when given, else 30, 60,
# 120, 240 s) and tries again, at most 5 times. Be polite: build-pack.sh caches the answer and reuses it.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
if [ "${1:-}" = --print-query ]; then
  OUT=""; BOX="${2:?W,S,E,N}"; DATE="${3:-}"
else
  OUT="${1:?out.osm}"; BOX="${2:?W,S,E,N}"; DATE="${3:-}"
fi
check_box "$BOX" 0.2
IFS=, read -r W S E N <<< "$BOX"
ENDPOINT="${OVERPASS_URL:-https://overpass-api.de/api/interpreter}"
SETTINGS="[out:xml][timeout:180][bbox:$S,$W,$N,$E]"
if [ -n "$DATE" ]; then
  [[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || die "date must look like 2026-10-15T06:13:50Z"
  SETTINGS="$SETTINGS[date:\"$DATE\"]"
fi
QUERY="$SETTINGS;
(
  nwr[\"piste:type\"];
  nwr[\"aerialway\"];
  nwr[\"landuse\"=\"winter_sports\"];
  nwr[\"amenity\"=\"snow_park\"];
  nwr[\"leisure\"=\"snow_park\"];
  nwr[\"man_made\"=\"piste:halfpipe\"];
  relation[\"route\"~\"^(piste|ski)$\"];
);
(._;>;);
out body;"
if [ -z "$OUT" ]; then
  printf '%s\n' "$QUERY"
  exit 0
fi

mkdir -p "$(dirname "$OUT")"
TMP="$OUT.part"; HDR="$OUT.headers"
trap 'rm -f "$TMP" "$HDR" "$OUT.query.part"' EXIT
for attempt in 1 2 3 4 5; do
  log "Overpass request $attempt for $BOX${DATE:+ at $DATE}"
  # curl prints 000 itself when it cannot connect; keep only the last three characters either way.
  code="$(curl -sS -A "$MAPS_USER_AGENT" --max-time 240 -D "$HDR" -o "$TMP" -w '%{http_code}' \
    --data-urlencode "data=$QUERY" "$ENDPOINT")" || true
  code="${code: -3}"
  [[ "$code" =~ ^[0-9]{3}$ ]] || code=000
  if [ "$code" = 200 ]; then
    if grep -q '<remark>' "$TMP"; then
      log "Overpass answered with a remark: $(grep -o '<remark>[^<]*' "$TMP" | head -1 | cut -c9-200)"
    elif grep -q 'osm_base=' "$TMP" && tail -c 200 "$TMP" | grep -q '</osm>'; then
      # The old record goes first: an answer without its record is never reused, so a run cut short here only
      # costs a new request.
      rm -f "$OUT.query"
      mv "$TMP" "$OUT"
      printf '%s\n' "$QUERY" > "$OUT.query.part"
      mv "$OUT.query.part" "$OUT.query"
      log "saved $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"
      exit 0
    else
      log "Overpass answer is incomplete"
    fi
  elif [[ ! "$code" =~ ^(000|429|502|503|504)$ ]]; then
    die "Overpass returned HTTP $code"
  fi
  [ "$attempt" -lt 5 ] || break
  wait_s="$(awk 'tolower($1)=="retry-after:" {gsub("\r",""); print $2}' "$HDR" 2>/dev/null | head -1)"
  [[ "$wait_s" =~ ^[0-9]+$ ]] || wait_s=$((30 * (1 << (attempt - 1))))
  log "HTTP $code; waiting ${wait_s}s before trying again"
  sleep "$wait_s"
done
die "Overpass did not answer after 5 attempts; try later, or pass a saved answer with --osm-file"

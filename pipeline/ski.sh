# The steps that make a pack's ski file, <key>-ski.pmtiles (ADR-036): runs, run areas, lifts, lift stations, the
# ski-area outline and 20 m contours, from OpenStreetMap data (Overpass) and an elevation model. Sourced (not run) by
# build-pack.sh, which makes whole packs, and by build-ski.sh, which makes the ski file alone. Needs lib.sh sourced
# first, CACHE set, and the options OSM_FILE, REFRESH_OSM and OSM_DATE_ARG ("", "recorded", "current" or a timestamp).

CONTOUR_INTERVAL_M=20   # pack-schema.json contours.interval_m; the 100 m index lines are marked in ski-overlay.yml
CONTOUR_GRID_M=10

# dem_path / contours_path <work dir> <elevation source>: the cached elevation window and contours of a work folder,
# both named after their source, so a source changed under a key that never shipped gets its own window and contours
# (the hillshade and the contours always come from one model). forget_stale_cuts (lib.sh) drops all of them when the
# box changes.
dem_path() { echo "$1/dem-$2.tif"; }
contours_path() { echo "$1/contours-$2-${CONTOUR_INTERVAL_M}m.gpkg"; }

# check_osm_date_arg: refuses a malformed --osm-date before any work.
check_osm_date_arg() {
  case "$OSM_DATE_ARG" in
    ''|recorded|current) return 0 ;;
  esac
  [[ "$OSM_DATE_ARG" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] \
    || die "--osm-date must be recorded, current or a timestamp like 2026-10-15T06:13:50Z"
}

verify_profile() {
  local vlog="$CACHE/planetiler-verify.log"
  docker run --rm -u "$(id -u):$(id -g)" -v "$PIPE:/p:ro" "$PLANETILER_IMAGE" verify /p/ski-overlay.yml > "$vlog" 2>&1 || true
  # planetiler verify exits 0 even when an example fails, so read its summary.
  if ! python3 -I "$PIPE/packlib.py" verify-log "$vlog"; then
    sed 's/\x1b\[[0-9;]*m//g' "$vlog" | grep -E "FAIL|passed|failed|rror" >&2 || true
    die "pipeline/ski-overlay.yml failed planetiler verify (see $vlog)"
  fi
  log "ski-overlay.yml: planetiler verify passed"
}

# resolve_osm_date: sets OSM_DATE for the resort in KEY/SLUG from OSM_DATE_ARG. "recorded" is the timestamp the pack
# was built from (osm_timestamp in resorts.json, else in $PACKS_DIR/<key>/pack.json, packs/ by default); "" and
# "current" mean the cached answer or the current data.
resolve_osm_date() {
  case "$OSM_DATE_ARG" in
    ''|current) OSM_DATE="" ;;
    recorded)
      OSM_DATE="$(python3 -I "$PIPE/packlib.py" recorded osm_timestamp "$MAPS_ROOT/resorts.json" "$SLUG" "${PACKS_DIR:-$MAPS_ROOT/packs}/$KEY/pack.json")" \
        || die "--osm-date=recorded: no recorded OSM timestamp for $KEY (pass --osm-date=current for the current data)"
      log "OSM: the recorded data of $KEY, $OSM_DATE" ;;
    *) OSM_DATE="$OSM_DATE_ARG" ;;
  esac
}

# fetch_osm <slug> <box>: sets OSM_RAW, OSM_BASE, OSM_QBOX (the box asked for: the box plus the margin) and
# OSM_ANSWER_BOX (the box the answer covers, which the pack records: OSM_QBOX, or a saved answer's own bounds).
# A cached answer is reused only when its record (<answer>.query, written by overpass.sh) is the exact query this
# run would send: the same box with its margin, the same date and the same selection. Any other cached answer (an
# older query, a smaller margin, a saved answer copied in, or one without a record) is fetched again, so a pack is
# always built from the data its record names, as a rebuild from the public repository fetches it.
fetch_osm() {
  local slug="$1" box="$2" dir="$CACHE/$1" raw query
  OSM_QBOX="$(python3 -I "$PIPE/packlib.py" expand "$box" 0.04 0.02)"
  mkdir -p "$dir"
  raw="$dir/overpass.osm"
  [ -z "$OSM_DATE" ] || raw="$dir/overpass-${OSM_DATE//:/}.osm"
  query="$(bash "$PIPE/overpass.sh" --print-query "$OSM_QBOX" "$OSM_DATE")" || die "cannot form the Overpass query for $OSM_QBOX"
  if [ -n "$OSM_FILE" ]; then
    [ -s "$OSM_FILE" ] || die "--osm-file $OSM_FILE is missing or empty"
    # Not the answer to this pipeline's query: without a record it is never reused as a cached answer.
    rm -f "$raw.query"
    cp "$OSM_FILE" "$raw.part" && mv "$raw.part" "$raw"
    log "OSM: using the saved answer $OSM_FILE"
  elif [ ! -s "$raw" ] || [ "$REFRESH_OSM" = 1 ]; then
    bash "$PIPE/overpass.sh" "$raw" "$OSM_QBOX" "$OSM_DATE"
  elif [ "$(cat "$raw.query" 2>/dev/null)" != "$query" ]; then
    log "OSM: the cached answer $raw was not made with this query (box $OSM_QBOX${OSM_DATE:+, data of $OSM_DATE}); asking Overpass again"
    bash "$PIPE/overpass.sh" "$raw" "$OSM_QBOX" "$OSM_DATE"
  else
    log "OSM: cached answer $raw"
  fi
  local OSM_BOUNDS="" info
  # With --osm-date the data timestamp is that date (Overpass reports its current time in a date-pinned answer).
  info="$(python3 -I "$PIPE/packlib.py" osm-info "$raw" "$OSM_DATE")" || die "$raw is not a usable Overpass answer"
  eval "$info"
  [ -n "$OSM_BOUNDS" ] || die "$raw has no <bounds>; cannot check that it covers the box"
  python3 -I "$PIPE/packlib.py" covers "$OSM_BOUNDS" "$box" \
    || die "the Overpass answer ($OSM_BOUNDS) does not cover the box $box; run with --refresh-osm"
  if [ -n "$OSM_FILE" ]; then
    python3 -I "$PIPE/packlib.py" covers "$OSM_BOUNDS" "$OSM_QBOX" \
      || log "note: the saved answer covers the box but not the whole query margin $OSM_QBOX; features lying wholly in the margin are missing from the edge tiles. The pack records the answer's own bounds."
    OSM_ANSWER_BOX="$OSM_BOUNDS"
  else
    python3 -I "$PIPE/packlib.py" covers "$OSM_BOUNDS" "$OSM_QBOX" \
      || die "the Overpass answer $raw ($OSM_BOUNDS) does not cover the box it was asked for, $OSM_QBOX"
    OSM_ANSWER_BOX="$OSM_QBOX"
  fi
  OSM_RAW="$raw"
}

# build_ski <work dir>: OSM answer -> normalize_osm.py -> osmium (PBF with the data timestamp) -> coverage.py ->
# elevation window -> contours -> Planetiler. Needs the resort's assignments from `packlib.py resort` (SLUG, KEY, BOX,
# ELEV, OSM_CREDIT_HTML, TERRAIN_CREDIT_HTML); sets OSM_DATE, OSM_RAW, OSM_BASE, OSM_QBOX, OSM_ANSWER_BOX and DEM,
# which the caller declares local. Writes <wk>/ski.pmtiles, <wk>/coverage.json and <wk>/normalize.json.
build_ski() {
  local wk="$1"
  forget_stale_cuts "$wk" "$BOX"

  # OSM: Overpass answer -> normalised XML (relation tags, overrides, flags, glyph filter) -> PBF -> coverage.
  resolve_osm_date
  fetch_osm "$SLUG" "$BOX"
  python3 -I "$PIPE/normalize_osm.py" --resorts "$MAPS_ROOT/resorts.json" --schema "$MAPS_ROOT/pack-schema.json" \
    --slug "$SLUG" --in "$OSM_RAW" --osm-base "$OSM_BASE" \
    --out-osm "$wk/ski.osm" --out-features "$wk/features.geojson" --out-report "$wk/normalize.json"
  ensure_osmium_image
  osmium_run sort --overwrite --output-header="osmosis_replication_timestamp=$OSM_BASE" \
    -o "$(in_root "$wk/ski.osm.pbf")" "$(in_root "$wk/ski.osm")"
  python3 -I "$PIPE/coverage.py" --features "$wk/features.geojson" --box="$BOX" --out "$wk/coverage.json" \
    --slug "$SLUG" --key "$KEY" --osm-base "$OSM_BASE" --resorts "$MAPS_ROOT/resorts.json" \
    --zooms "$(python3 -I "$PIPE/packlib.py" run-zooms "$MAPS_ROOT/pack-schema.json")" \
    || die "coverage check failed for $KEY (see $wk/coverage.json)"

  # Elevation: the box plus 0.04 degrees, on the source's own grid.
  local dbox
  DEM="$(dem_path "$wk" "$ELEV")"
  dbox="$(python3 -I "$PIPE/packlib.py" expand "$BOX" 0.04 0.04)"
  [ -s "$DEM" ] || bash "$PIPE/fetch-dem.sh" "$ELEV" "$DEM" "$dbox"

  # Contours every 20 m, from that window.
  local contours
  contours="$(contours_path "$wk" "$ELEV")"
  [ -s "$contours" ] || bash "$PIPE/contours.sh" "$DEM" "$contours" "$BOX" "$CONTOUR_INTERVAL_M" "$CONTOUR_GRID_M"

  # The ski file with Planetiler, z9-14, with the linked credit in the archive metadata.
  mkdir -p "$CACHE/planetiler-tmp"
  rm -f "$wk/ski.pmtiles"
  docker run --rm -u "$(id -u):$(id -g)" -v "$MAPS_ROOT:/w" -w /w -e JAVA_TOOL_OPTIONS="-Xmx2g" "$PLANETILER_IMAGE" \
    generate-custom --schema=/w/pipeline/ski-overlay.yml --osm_path="$(in_root "$wk/ski.osm.pbf")" \
    --contours_path="$(in_root "$contours")" --output="$(in_root "$wk/ski.pmtiles")" --bounds="$BOX" \
    --tmpdir=/w/.cache/planetiler-tmp --force \
    --archive_attribution="$OSM_CREDIT_HTML; contours: $TERRAIN_CREDIT_HTML" > "$wk/planetiler.log" 2>&1 \
    || { tail -30 "$wk/planetiler.log" >&2; die "Planetiler failed for $KEY"; }
  if sed 's/\x1b\[[0-9;]*m//g' "$wk/planetiler.log" | grep -qE '(^|[[:space:]])ERR([[:space:]]|$)'; then
    sed 's/\x1b\[[0-9;]*m//g' "$wk/planetiler.log" | grep -m5 -E '(^|[[:space:]])ERR([[:space:]]|$)' >&2
    die "Planetiler logged errors for $KEY (see $wk/planetiler.log)"
  fi
}

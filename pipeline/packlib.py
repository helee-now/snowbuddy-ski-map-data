#!/usr/bin/env python3
"""Small helpers for build-pack.sh, kept in Python so they can be tested (test/pipeline.test.mjs).

  packlib.py check-box W,S,E,N [MAX_SQ_DEG]     exit 0 if the box is safe to extract, else 1 with the reason
  packlib.py expand W,S,E,N DLON DLAT           prints the box grown by DLON/DLAT degrees on each side
  packlib.py covers OUTER INNER                 exit 0 if box OUTER contains box INNER
  packlib.py dry-run-bytes LOG                  prints the archive size `pmtiles extract --dry-run` reported
  packlib.py osm-info OVERPASS.osm [DATE]       prints shell assignments OSM_BASE=... OSM_BOUNDS=W,S,E,N; DATE is
                                                the [date:...] the answer was asked for, which then is OSM_BASE
  packlib.py resort RESORTS.json SLUG           prints shell assignments for one resort (values shell-quoted; SKI_AREA
                                                is its ski-area id, or its ids comma-separated for several mountains),
                                                after checking the entry (its neighbours too)
  packlib.py slugs RESORTS.json                 prints every slug, one per line
  packlib.py run-zooms SCHEMA.json              prints MIN-MAX: the run layers' minzoom to the ski file's maxzoom
  packlib.py recorded FIELD RESORTS.json SLUG [PACK.json]
                                                prints a built pack's recorded osm_timestamp or ski_sha256: from the
                                                resort's entry (the public data repository's resorts.json carries
                                                them), else from its record packs/<key>/pack.json; exit 1 if none.
                                                A new version without a record yet takes the osm_timestamp of the
                                                newest earlier version's record (packs/<slug>-v<N>/pack.json), so a
                                                pack rebuilt for new elevation keeps its runs and lifts
  packlib.py tnm-tiles ANSWER.json PROJECT [LON] prints the GeoTIFF URLs of one 3DEP project in an answer of The
                                                National Map's product API, sorted (fetch-dem.sh 3dep1); tiles in
                                                several UTM zones keep the zone of LON, the window's centre
  packlib.py stac-assets ANSWER.json ASSET      prints the ASSET hrefs of the items in a STAC item search answer,
                                                sorted (fetch-dem.sh hrdem1)
  packlib.py lidar-plan COVERAGE_JSON MIN_PCT   what fetch-dem.sh does with a 1 m window whose coverage (dem.py
                                                coverage) it is given: prints `fill` (any pixel of the window missing,
                                                by the exact count) or `none`; exit 1 when the lidar holds less than
                                                MIN_PCT of the box, 2 when the coverage has no count of missing pixels
  packlib.py verify-log LOG                     exit 0 if a `planetiler verify` log passed every example
  packlib.py planetiler-errors LOG              exit 1, naming them, when a Planetiler log's data errors say a
                                                multipolygon was not drawn as written (it could not be built, or a
                                                member way was missing); 2 when the log has no data-errors block
  packlib.py published KEY PUBLISHED.json       prints `<sha256>  <file>` for each file of a published pack (the list
                                                of everything on the maps bucket, written by mark-published.mjs);
                                                exit 1 when KEY is not published, 2 when the list cannot be read
  packlib.py record OUT.json KEY=VALUE...       writes a JSON object (values that parse as JSON are kept typed)
  packlib.py key-format SCHEMA.json PACK.json   prints the pack format a build of the key gets: its committed record's
                                                pack_format (a rebuild reproduces a committed key's format), else the
                                                one new builds get (pack-schema.json pack_format)
  packlib.py format-roles SCHEMA.json FORMAT    prints the file roles of a format, in pack-schema.json's role order
  packlib.py previous-record PACKS_DIR KEY      prints the path of the newest earlier version's record
                                                (PACKS_DIR/<slug>-v<N>/pack.json, N below KEY's version); exit 1 if none
  packlib.py newest-published PUBLISHED.json SLUG
                                                prints the newest published key of a resort (its highest version on
                                                the maps bucket); exit 1 if none is published
  packlib.py same-inputs RECORD.json W,S,E,N OSM_TIMESTAMP PROTOMAPS_BUILD ELEVATION
                                                exit 0 when a build of these inputs is the record's own (box, OSM data,
                                                Protomaps build and elevation source), else 1 printing what differs

The box guard exists because `pmtiles extract` with an empty --bbox copies the whole planet (about 129 GB):
that happened during the research. Every extract goes through check-box first, then a dry run.
"""
import json
import math
import os
import re
import shlex
import sys

MAX_BOX_SQ_DEG = 0.1      # about 750 km2 at 50 N: far larger than any resort, far smaller than a region
MIN_BOX_SIDE_DEG = 0.01   # about 1 km
KEY_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*-v[1-9][0-9]*$')
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
OSM_ID_RE = re.compile(r'^(way|relation)/[1-9][0-9]*$')
PROJECT_RE = re.compile(r'^[A-Za-z0-9_]+$')


def parse_box(text):
    parts = str(text).split(',')
    if len(parts) != 4:
        raise ValueError(f'box must be W,S,E,N (got {text!r})')
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f'box values must be numbers (got {text!r})') from None
    if not all(math.isfinite(v) for v in vals):
        raise ValueError(f'box values must be finite (got {text!r})')
    return vals


def box_problem(text, max_sq_deg=MAX_BOX_SQ_DEG):
    """Returns None for a safe box, else the reason it is refused."""
    try:
        w, s, e, n = parse_box(text)
    except ValueError as err:
        return str(err)
    if not (-180.0 <= w < e <= 180.0):
        return f'need -180 <= W < E <= 180 (got W={w}, E={e})'
    if not (-85.0 <= s < n <= 85.0):
        return f'need -85 <= S < N <= 85 (got S={s}, N={n})'
    if e - w < MIN_BOX_SIDE_DEG or n - s < MIN_BOX_SIDE_DEG:
        return f'box sides must be at least {MIN_BOX_SIDE_DEG} degrees'
    area = (e - w) * (n - s)
    if area >= max_sq_deg:
        return f'box covers {area:.3f} square degrees; the limit is {max_sq_deg}'
    return None


def fmt(v):
    return format(round(v, 6), '.6f').rstrip('0').rstrip('.')


def dry_run_bytes(text):
    """`pmtiles extract --dry-run` ends with: 'Extract transferred 1.0 MB (overfetch 0.05) for an archive size
    of 995 kB'. Returns the archive size in bytes, or None when the line is missing."""
    m = re.search(r'archive size of\s+([0-9]+(?:\.[0-9]+)?)\s*(B|kB|KB|MB|GB|TB)\b', text)
    if not m:
        return None
    unit = {'B': 1, 'kB': 1e3, 'KB': 1e3, 'MB': 1e6, 'GB': 1e9, 'TB': 1e12}[m.group(2)]
    return int(float(m.group(1)) * unit)


OSM_DATE_RE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$')


def osm_info(path, date=None):
    """Reads the head of an Overpass XML answer for its data timestamp and bounds.

    For the answer to a date-pinned query ([date:"..."]) the data timestamp is the date asked for: Overpass still
    reports its current database time in <meta osm_base> (seen 2026-10-15: asked for 06:13:50Z, answered with
    osm_base 09:24:49Z), so the caller passes the date and it wins."""
    with open(path, encoding='utf-8', errors='replace') as f:
        head = f.read(65536)
    base = re.search(r'<meta\s[^>]*osm_base="([^"]+)"', head)
    b = re.search(r'<bounds\s+minlat="([-0-9.]+)"\s+minlon="([-0-9.]+)"\s+maxlat="([-0-9.]+)"\s+maxlon="([-0-9.]+)"', head)
    if not base:
        raise ValueError(f'{path}: no <meta osm_base=...>')
    if date is not None:
        if not OSM_DATE_RE.match(date):
            raise ValueError(f'the OSM date must look like 2026-10-15T06:13:50Z (got {date!r})')
        if date > base.group(1):
            raise ValueError(f'{path}: asked for the data at {date}, but the answer is from {base.group(1)}')
    bounds = f'{b.group(2)},{b.group(1)},{b.group(4)},{b.group(3)}' if b else ''
    return date or base.group(1), bounds


DERIVED_BUFFER_RANGE_M = (10.0, 1000.0)   # normalize_osm.py DERIVED_BUFFER_RANGE_M


def ski_area_ids(entry, slug):
    """The OSM ids of a resort's ski area: `ski_area` is one id (way/123 or relation/123), a list of at least two
    distinct ids for a resort of several mountains on one map (each its own landuse=winter_sports polygon), or
    "derived" (no ids: the area is derived from the resort's lifts and runs, buffered by `ski_area_buffer_m`, a number
    of metres from 10 to 1000, 100 when absent; normalize_osm.py)."""
    sa = entry.get('ski_area')
    if sa == 'derived':
        buffer_m = entry.get('ski_area_buffer_m', 100)
        lo, hi = DERIVED_BUFFER_RANGE_M
        if isinstance(buffer_m, bool) or not isinstance(buffer_m, (int, float)) or not lo <= buffer_m <= hi:
            raise ValueError(f'{slug}: ski_area_buffer_m must be a number of metres from {lo:g} to {hi:g}')
        return []
    if 'ski_area_buffer_m' in entry:
        raise ValueError(f'{slug}: ski_area_buffer_m goes only with "ski_area": "derived"')
    if isinstance(sa, str) and OSM_ID_RE.match(sa):
        return [sa]
    if (isinstance(sa, list) and len(sa) >= 2 and all(isinstance(x, str) and OSM_ID_RE.match(x) for x in sa)
            and len(set(sa)) == len(sa)):
        return list(sa)
    raise ValueError(f'{slug}: ski_area must look like way/123 or relation/123, be a list of at least two distinct such ids, or be "derived"')


NEIGHBOUR_KEYS = {'id', 'name', 'reason'}


def neighbour_entries(entry, slug, ski_ids):
    """A resort's `neighbours`: other resorts' ski areas inside its box, left out of its map (owner decision
    2026-10-21). Each is {"id": way/… or relation/…, "name": its OSM name tag, as OSM has it, "reason": why}; the ids
    are distinct and none is one of the resort's own. Optional: [] when absent."""
    nb = entry.get('neighbours')
    if nb is None:
        return []
    if not isinstance(nb, list) or not nb:
        raise ValueError(f'{slug}: neighbours must be a list of {{"id", "name", "reason"}} objects (leave it out for none)')
    seen = set()
    for i, n in enumerate(nb):
        where = f'{slug}: neighbours[{i}]'
        if not isinstance(n, dict) or set(n) != NEIGHBOUR_KEYS:
            raise ValueError(f'{where} must hold exactly id, name and reason')
        if not isinstance(n['id'], str) or not OSM_ID_RE.match(n['id']):
            raise ValueError(f'{where}: id must look like way/123 or relation/123')
        if not isinstance(n['name'], str) or not n['name'].strip():
            raise ValueError(f'{where} ({n["id"]}): name must be the OSM name tag of that ski area')
        if not isinstance(n['reason'], str) or not n['reason'].strip():
            raise ValueError(f'{where} ({n["id"]}): every neighbour needs a reason')
        if n['id'] in seen:
            raise ValueError(f'{where}: {n["id"]} appears twice')
        if n['id'] in ski_ids:
            raise ValueError(f'{where}: {n["id"]} is the resort\'s own ski area')
        seen.add(n['id'])
    return nb


def resort_entry(resorts, slug):
    entry = next((r for r in resorts['resorts'] if r.get('slug') == slug), None)
    if entry is None:
        raise ValueError(f'no resort {slug!r}; known: {", ".join(r["slug"] for r in resorts["resorts"])}')
    if not SLUG_RE.match(slug):
        raise ValueError(f'bad slug {slug!r}')
    key = entry.get('key', '')
    if not KEY_RE.match(key) or key != f'{slug}-v{entry.get("version")}':
        raise ValueError(f'{slug}: key must be <slug>-v<version> (got {key!r}, version {entry.get("version")!r})')
    box = ','.join(fmt(v) for v in entry['box'])
    problem = box_problem(box)
    if problem:
        raise ValueError(f'{slug}: {problem}')
    ski_ids = ski_area_ids(entry, slug)
    neighbour_entries(entry, slug, ski_ids)
    elev = resorts.get('elevation_sources', {}).get(entry.get('elevation'))
    if elev is None:
        raise ValueError(f'{slug}: elevation source {entry.get("elevation")!r} is not in elevation_sources')
    if not re.search(r'<a href="https://[^"]+">', elev.get('credit_html', '')):
        raise ValueError(f'{slug}: the elevation credit must be linked HTML (<a href="https://...">)')
    project = entry.get('elevation_project', '')
    if project and not PROJECT_RE.match(project):
        raise ValueError(f'{slug}: bad elevation_project {project!r}')
    if elev.get('needs_project') and not project:
        raise ValueError(f'{slug}: elevation source {entry["elevation"]!r} needs elevation_project (the tiles to read)')
    if project and not elev.get('needs_project'):
        raise ValueError(f'{slug}: elevation source {entry["elevation"]!r} takes no elevation_project')
    smooth = elev.get('contour_smoothing_m', 0)
    if not isinstance(smooth, (int, float)) or isinstance(smooth, bool) or not 0 <= smooth <= 100:
        raise ValueError(f'{slug}: contour_smoothing_m must be a number of metres from 0 to 100')
    return {
        'SLUG': slug, 'KEY': key, 'VERSION': str(entry['version']), 'BOX': box,
        'SKI_AREA': ','.join(ski_ids) or 'derived', 'ELEV': entry['elevation'], 'ELEV_RES': str(elev['resolution_m']),
        'ELEV_PROJECT': project, 'CONTOUR_SMOOTH_M': fmt(float(smooth)),
        'OSM_CREDIT_HTML': resorts['credits']['osm_html'], 'TERRAIN_CREDIT_HTML': elev['credit_html'],
    }


def earlier_record(pack_json, slug, field):
    """The field from the newest record of an earlier version of the resort, next to PACK.json's folder
    (packs/<slug>-v<N>/pack.json with N below the version in PACK.json's folder name), as (value, folder) or None."""
    folder = os.path.dirname(os.path.abspath(pack_json))
    m = re.match(rf'^{re.escape(slug)}-v([1-9][0-9]*)$', os.path.basename(folder))
    if not m:
        return None
    version = int(m.group(1))
    packs = os.path.dirname(folder)
    found = []
    for name in os.listdir(packs) if os.path.isdir(packs) else []:
        mm = re.match(rf'^{re.escape(slug)}-v([1-9][0-9]*)$', name)
        if mm and int(mm.group(1)) < version and os.path.exists(os.path.join(packs, name, 'pack.json')):
            found.append((int(mm.group(1)), name))
    for _, name in sorted(found, reverse=True):
        with open(os.path.join(packs, name, 'pack.json'), encoding='utf-8') as f:
            value = json.load(f).get(field)
        if value:
            return value, name
    return None


HTTPS_TIF_RE = re.compile(r'^https://[A-Za-z0-9.-]+/[A-Za-z0-9._/~%+-]+\.tif$')
# The UTM zone in a 3DEP 1 m tile's name (USGS_1M_11_x24y432_<project>.tif); the older names (USGS_one_meter_x…)
# carry none.
TNM_ZONE_RE = re.compile(r'/USGS_1M_(\d{1,2})_x\d+y\d+_')


def utm_zone(lon):
    """The UTM zone of a longitude (1 to 60)."""
    return min(60, int((float(lon) + 180) // 6) + 1)


def tnm_tiles(doc, project, lon=None):
    """The GeoTIFF URLs of one 3DEP project in a TNM product API answer, sorted. Refuses an answer that says it
    holds more products than it lists (another page would be needed). A project near a UTM zone boundary delivers
    tiles in both zones (CA_SierraNevada_B22 and NV_USFSR4_D23 at Lake Tahoe, 120° W: zone 10 and zone 11 tiles over
    the same ground, each zone's set whole only on its own side), and gdalbuildvrt mosaics one projection, skipping
    the rest with a warning: the lidar then seemed to hold 63% of Heavenly's box (2026-10-31). When the tiles span
    zones, only the zone of `lon` (the window's centre) is kept; without it such an answer is refused."""
    if not PROJECT_RE.match(project or ''):
        raise ValueError(f'bad 3DEP project {project!r}')
    items = doc.get('items')
    if not isinstance(items, list):
        raise ValueError('not a product API answer (no items)')
    total = doc.get('total')
    if isinstance(total, int) and total > len(items):
        raise ValueError(f'the answer lists {len(items)} of {total} products; ask for more per page')
    urls = set()
    for it in items:
        url = it.get('downloadURL') if isinstance(it, dict) else None
        if isinstance(url, str) and f'/Projects/{project}/TIFF/' in url:
            if not HTTPS_TIF_RE.match(url):
                raise ValueError(f'unexpected tile URL {url!r}')
            urls.add(url)
    by_zone = {}
    for url in urls:
        m = TNM_ZONE_RE.search(url)
        by_zone.setdefault(int(m.group(1)) if m else None, set()).add(url)
    if len(by_zone) > 1:
        zones = ', '.join(str(z) for z in sorted(by_zone, key=lambda z: (z is None, z or 0)))
        if lon is None:
            raise ValueError(f'{project} has tiles in UTM zones {zones}: pass the window centre longitude to keep one')
        zone = utm_zone(lon)
        if zone not in by_zone:
            raise ValueError(f'{project} has tiles in UTM zones {zones}, none in zone {zone}, the window centre\'s')
        urls = by_zone[zone]
    return sorted(urls)


class LidarRefused(ValueError):
    """The lidar holds too little of the box for a 1 m source."""


def lidar_plan(coverage, min_box_pct):
    """'fill' or 'none' for a 1 m window with this coverage (dem.py coverage); LidarRefused when the lidar holds too
    little of the box, so the resort stays on a coarser model rather than a mosaic of two resolutions. Holes are
    filled whenever any pixel of the window is missing, by the exact count: the shares are rounded to 3 decimals and
    read 100.0 with up to about 128 pixels missing in a Mammoth-sized window, which would have stayed holes. KeyError
    or ValueError without a valid count."""
    box_pct = float(coverage['box_pct'])
    if box_pct < min_box_pct:
        raise LidarRefused(f'the lidar holds {box_pct}% of the box, under {min_box_pct}%')
    missing = coverage['window_missing_px']
    if not isinstance(missing, int) or isinstance(missing, bool) or missing < 0:
        raise ValueError(f'bad count of missing pixels {missing!r}')
    return 'fill' if missing > 0 else 'none'


def stac_assets(doc, asset):
    """The hrefs of one asset of every item in a STAC item search answer, sorted. Refuses a partial answer."""
    feats = doc.get('features')
    if not isinstance(feats, list):
        raise ValueError('not a STAC item search answer (no features)')
    matched = doc.get('numberMatched')
    if (isinstance(matched, int) and matched > len(feats)) or any(isinstance(l, dict) and l.get('rel') == 'next' for l in doc.get('links') or []):
        raise ValueError('the answer has more items than it lists; ask for more per page')
    urls = set()
    for f in feats:
        href = ((f.get('assets') or {}).get(asset) or {}).get('href') if isinstance(f, dict) else None
        if href is None:
            continue
        if not isinstance(href, str) or not HTTPS_TIF_RE.match(href):
            raise ValueError(f'unexpected asset URL {href!r}')
        urls.add(href)
    return sorted(urls)


SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
FILE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')


def published_files(doc, key):
    """The (file, sha256) pairs of a published pack, sorted by file, or None when KEY is not published."""
    if not KEY_RE.match(key or ''):
        raise ValueError(f'bad key {key!r}')
    if not isinstance(doc, dict) or doc.get('format') != 1 or not isinstance(doc.get('packs'), dict):
        raise ValueError('not a published list of format 1')
    entry = doc['packs'].get(key)
    if entry is None:
        return None
    files = entry.get('files') if isinstance(entry, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError(f'{key}: the published entry lists no files')
    for name, sha in files.items():
        if not FILE_RE.match(name) or not isinstance(sha, str) or not SHA256_RE.match(sha):
            raise ValueError(f'{key}: a malformed file entry')
    return sorted(files.items())


def verify_log_ok(text):
    clean = re.sub(r'\x1b\[[0-9;]*m', '', text)
    return bool(re.search(r'^\s*[1-9][0-9]* passed\s*$', clean, re.M)) and not re.search(r'\bFAIL\b|\bfailed\b', clean)


# Planetiler's data errors (INF lines at the end of its log) that mean a multipolygon is not in the tiles as written:
# it could not be built (osm_invalid_multipolygon and its variants, after a prefix such as feature_polygon_), or a
# member way was missing. Planetiler logs them only as information and draws nothing for that polygon. Others are not
# refused: render_snap_fix_input (a polygon mended after snapping to the tile grid) is in every pilot's log, and
# osm_multipolygon_duplicate_member (a way listed twice) is drawn from one copy, as OSM data can hold it.
REFUSED_DATA_ERROR_RE = re.compile(r'invalid_multipolygon|multipolygon_missing_way')


def planetiler_data_errors(text):
    """The data errors at the end of a Planetiler log, {name: count}; None when the log has no data-errors block."""
    lines = re.sub(r'\x1b\[[0-9;]*m', '', text).splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip().endswith(' - data errors:')), None)
    if start is None:
        return None
    errors = {}
    for line in lines[start + 1:]:
        m = re.search(r' - \t([A-Za-z0-9_]+)\t([0-9]+)\s*$', line)
        if not m:
            break
        errors[m.group(1)] = int(m.group(2))
    return errors


def key_format(schema, record_path):
    """The format a build of the key gets: its committed record's (a rebuild of a committed key reproduces it), else
    pack-schema.json's pack_format. Refuses a format pack-schema.json does not define."""
    fmt = schema['pack_format']
    if record_path and os.path.exists(record_path):
        with open(record_path, encoding='utf-8') as f:
            fmt = json.load(f).get('pack_format', 1)
    if isinstance(fmt, bool) or not isinstance(fmt, int) or str(fmt) not in schema['formats']:
        raise ValueError(f'pack format {fmt!r} is not one pack-schema.json defines')
    return fmt


def format_roles(schema, fmt):
    roles = schema['formats'].get(str(fmt), {}).get('roles')
    if roles is None:
        raise ValueError(f'format {fmt!r} is not defined in pack-schema.json')
    return [r for r in schema['roles'] if r in roles]


def previous_record(packs_dir, key):
    """The newest earlier version's record of KEY's resort in packs_dir, or None."""
    m = re.match(r'^(.+)-v([1-9][0-9]*)$', key or '')
    if not m or not KEY_RE.match(key):
        raise ValueError(f'bad key {key!r}')
    slug, version = m.group(1), int(m.group(2))
    found = []
    for name in os.listdir(packs_dir) if os.path.isdir(packs_dir) else []:
        mm = re.match(rf'^{re.escape(slug)}-v([1-9][0-9]*)$', name)
        if mm and int(mm.group(1)) < version and os.path.exists(os.path.join(packs_dir, name, 'pack.json')):
            found.append((int(mm.group(1)), name))
    return os.path.join(packs_dir, max(found)[1], 'pack.json') if found else None


def newest_published(doc, slug):
    if not SLUG_RE.match(slug or ''):
        raise ValueError(f'bad slug {slug!r}')
    if not isinstance(doc, dict) or doc.get('format') != 1 or not isinstance(doc.get('packs'), dict):
        raise ValueError('not a published list of format 1')
    found = []
    for key in doc['packs']:
        m = re.match(rf'^{re.escape(slug)}-v([1-9][0-9]*)$', key)
        if m:
            found.append((int(m.group(1)), key))
    return max(found)[1] if found else None


def input_differences(record, box, osm_timestamp, protomaps_build, elevation):
    """What differs between a record's inputs and a build's: box, OSM data, Protomaps build, elevation source."""
    out = []
    if [float(v) for v in record.get('box', [])] != [float(v) for v in box.split(',')]:
        out.append('box')
    if record.get('osm_timestamp') != osm_timestamp:
        out.append('OSM data')
    if record.get('protomaps_build') != protomaps_build:
        out.append('Protomaps build')
    if (record.get('elevation') or {}).get('source') != elevation:
        out.append('elevation source')
    return out


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == 'check-box':
            limit = float(args[1]) if len(args) > 1 else MAX_BOX_SQ_DEG
            if not 0 < limit <= 1.0:
                raise ValueError('the area limit must be above 0 and at most 1 square degree')
            problem = box_problem(args[0] if args else '', limit)
            if problem:
                print(f'refused box: {problem}', file=sys.stderr)
                return 1
            return 0
        if cmd == 'expand':
            w, s, e, n = parse_box(args[0])
            dx, dy = float(args[1]), float(args[2])
            print(','.join(fmt(v) for v in (w - dx, s - dy, e + dx, n + dy)))
            return 0
        if cmd == 'covers':
            ow, os_, oe, on = parse_box(args[0])
            iw, is_, ie, in_ = parse_box(args[1])
            return 0 if (ow <= iw and os_ <= is_ and oe >= ie and on >= in_) else 1
        if cmd == 'dry-run-bytes':
            with open(args[0], encoding='utf-8', errors='replace') as f:
                size = dry_run_bytes(f.read())
            if size is None:
                print('no "archive size of" line in the dry-run log', file=sys.stderr)
                return 1
            print(size)
            return 0
        if cmd == 'osm-info':
            base, bounds = osm_info(args[0], args[1] if len(args) > 1 and args[1] else None)
            print(f'OSM_BASE={shlex.quote(base)}\nOSM_BOUNDS={shlex.quote(bounds)}')
            return 0
        if cmd == 'resort':
            with open(args[0], encoding='utf-8') as f:
                resorts = json.load(f)
            for k, v in resort_entry(resorts, args[1]).items():
                print(f'{k}={shlex.quote(v)}')
            return 0
        if cmd == 'slugs':
            with open(args[0], encoding='utf-8') as f:
                for r in json.load(f)['resorts']:
                    print(r['slug'])
            return 0
        if cmd == 'run-zooms':
            with open(args[0], encoding='utf-8') as f:
                schema = json.load(f)
            lo = min(schema['ski_layers'][layer]['minzoom'] for layer in ('piste', 'piste_area'))
            print(f'{lo}-{schema["roles"]["ski"]["maxzoom"]}')
            return 0
        if cmd == 'recorded':
            field, resorts_path, slug = args[0], args[1], args[2]
            if field not in ('osm_timestamp', 'ski_sha256'):
                raise ValueError(f'unknown field {field!r}')
            with open(resorts_path, encoding='utf-8') as f:
                entry = next((r for r in json.load(f)['resorts'] if r.get('slug') == slug), None)
            if entry is None:
                raise ValueError(f'no resort {slug!r}')
            value = entry.get('osm_timestamp') if field == 'osm_timestamp' else (entry.get('ski_file') or {}).get('sha256')
            if not value and len(args) > 3 and os.path.exists(args[3]):
                with open(args[3], encoding='utf-8') as f:
                    record = json.load(f)
                value = record.get('osm_timestamp') if field == 'osm_timestamp' else next(
                    (x['sha256'] for x in record.get('files', []) if x.get('role') == 'ski'), None)
            elif not value and len(args) > 3 and field == 'osm_timestamp':
                # A new version: the OSM data of the newest earlier version, never its ski file's hash.
                earlier = earlier_record(args[3], slug, field)
                if earlier:
                    value = earlier[0]
                    print(f'packlib recorded: no record of this version yet; the OSM data of {earlier[1]}', file=sys.stderr)
            if not value:
                return 1
            print(value)
            return 0
        if cmd == 'lidar-plan':
            try:
                print(lidar_plan(json.loads(args[0]), float(args[1])))
            except LidarRefused as err:
                print(f'packlib lidar-plan: {err}', file=sys.stderr)
                return 1
            return 0
        if cmd in ('tnm-tiles', 'stac-assets'):
            with open(args[0], encoding='utf-8') as f:
                doc = json.load(f)
            urls = tnm_tiles(doc, args[1], args[2] if len(args) > 2 else None) if cmd == 'tnm-tiles' else stac_assets(doc, args[1])
            for url in urls:
                print(url)
            return 0
        if cmd == 'published':
            with open(args[1], encoding='utf-8') as f:
                files = published_files(json.load(f), args[0])
            if files is None:
                return 1
            for name, sha in files:
                print(f'{sha}  {name}')
            return 0
        if cmd == 'verify-log':
            with open(args[0], encoding='utf-8', errors='replace') as f:
                return 0 if verify_log_ok(f.read()) else 1
        if cmd == 'planetiler-errors':
            with open(args[0], encoding='utf-8', errors='replace') as f:
                errors = planetiler_data_errors(f.read())
            if errors is None:
                raise ValueError('the log has no "data errors:" block (did Planetiler finish?)')
            refused = {k: v for k, v in sorted(errors.items()) if REFUSED_DATA_ERROR_RE.search(k)}
            for k, v in refused.items():
                print(f'packlib planetiler-errors: {k} {v}', file=sys.stderr)
            return 1 if refused else 0
        if cmd == 'key-format':
            with open(args[0], encoding='utf-8') as f:
                schema = json.load(f)
            print(key_format(schema, args[1] if len(args) > 1 else ''))
            return 0
        if cmd == 'format-roles':
            with open(args[0], encoding='utf-8') as f:
                schema = json.load(f)
            print(' '.join(format_roles(schema, args[1])))
            return 0
        if cmd == 'previous-record':
            path = previous_record(args[0], args[1])
            if path is None:
                return 1
            print(path)
            return 0
        if cmd == 'newest-published':
            with open(args[0], encoding='utf-8') as f:
                key = newest_published(json.load(f), args[1])
            if key is None:
                return 1
            print(key)
            return 0
        if cmd == 'same-inputs':
            with open(args[0], encoding='utf-8') as f:
                record = json.load(f)
            diff = input_differences(record, args[1], args[2], args[3], args[4])
            if diff:
                print(', '.join(diff))
                return 1
            return 0
        if cmd == 'record':
            doc = {}
            for kv in args[1:]:
                k, _, v = kv.partition('=')
                try:
                    doc[k] = json.loads(v)
                except ValueError:
                    doc[k] = v
            with open(args[0], 'w', encoding='utf-8') as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
                f.write('\n')
            return 0
    except (ValueError, IndexError, OSError, KeyError) as err:
        print(f'packlib {cmd}: {err}', file=sys.stderr)
        return 2
    print(f'unknown command {cmd!r}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

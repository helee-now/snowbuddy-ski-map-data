#!/usr/bin/env python3
"""Normalises one resort's Overpass answer (OSM XML) into the input of the ski overlay (ADR-036).

In order, it:
  1. copies piste tags from route relations (type=route or superroute, with a piste:type) onto member ways that
     lack them: piste:type, piste:difficulty, piste:grooming, patrolled, the name (only when the way has no name of
     its own) and the ref. Routes of a kept type (downhill and the others the map draws) go first, so a way shared
     by a downhill route and a ski-touring or nordic one stays a run; within each group, in relation id order;
  2. applies the resort's overrides file (resorts/<slug>.overrides.json): renamed or hidden names, rating
     corrections, park flags, out-of-bounds flags and hidden elements. Every entry carries a reason. An entry whose
     `expect` no longer matches OSM, or whose element is gone, stops the build, so a fix made in OSM is never
     silently overwritten;
  3. keeps only what the map draws, with the attributes the style needs:
       piste, piste_area  downhill, snow_park, playground and connection runs. Nordic, ski-touring and snowshoe
                          trails are left out (owner decision 2026-10-15), and so are the other winter trails
                          (hiking, sledding, sleigh rides), which the map does not draw. Difficulty is normalised;
                          ungroomed, gladed and park are derived; out_of_bounds marks a run that lies mostly outside
                          the ski-area polygon and is tagged piste:grooming=backcountry or patrolled=no (on the way,
                          or on its route relation through step 1). Those runs
                          stay in the file and the style draws them in their own out-of-bounds style (owner
                          decision 2026-10-15);
       lift               aerialway in the lift list. Zip lines and goods lifts are dropped; lifecycle keys such as
                          proposed:aerialway are ignored, so only `aerialway` decides;
       lift_station       aerialway=station within 100 m of a kept lift, and the two ends of every kept lift (its
                          bottom and top terminals) unless a station is already within 40 m of the end;
       ski_area           the resort's own polygon, picked by its OSM id;
  4. ranks every run line by importance (sb:rank, for the style's overview zooms): 1 for the trunk runs, in each
     rating the style draws in its own colour (easy, intermediate, advanced, expert, park, unrated) the longest named
     runs that together make up half of that rating's named in-bounds run length; 3 for runs under 300 m (a named
     run's length summed over all its ways, an unnamed way's own length); 2 for the others;
  5. reduces every string to the glyph ranges the app bundles (ADR-015).

orient.py then turns runs downhill and lifts uphill from the elevation model (ski.sh runs it after the contours).

Outputs: an OSM XML file whose elements carry only `sb:*` tags (osmium turns it into the PBF that
ski-overlay.yml reads through Planetiler), a GeoJSON file of the kept features (read by coverage.py) and a JSON
report. No OSM user names, user ids or changesets are written.

Usage:
  python3 -I normalize_osm.py --resorts resorts.json --schema pack-schema.json --slug big-white \
      --in overpass.osm --out-osm normalized.osm --out-features features.geojson --out-report normalize.json \
      [--overrides resorts/big-white.overrides.json] [--allow-stale-overrides] [--osm-base TIMESTAMP]

--osm-base gives the data timestamp when the answer's own <meta osm_base> is not it: a date-pinned Overpass query
([date:"..."]) still reports the server's current time there (packlib.py osm-info decides, build-pack.sh passes it).

Exit codes: 0 done, 2 bad input or configuration, 3 stale overrides.
"""
import argparse
import json
import math
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

EARTH_RADIUS_M = 6371008.8
# A backcountry or unpatrolled run counts as out of bounds when less than this share of its length (or, for a run
# area, of its outline) lies inside the ski-area polygon. Gated routes that start inside the boundary and leave it
# stay out of bounds; in-bounds bowls tagged backcountry (lying wholly inside) stay in bounds.
OOB_MAX_INSIDE_FRACTION = 0.5
STATION_MAX_DISTANCE_M = 100.0
DENSIFY_STEP_M = 10.0
OVERRIDE_SET_KEYS = {'name', 'difficulty', 'park', 'out_of_bounds'}
UNGROOMED_GROOMING = {'backcountry', 'mogul', 'no'}
UNGROOMED_DIFFICULTY = {'freeride', 'extreme'}
PARK_TAGS = (('amenity', 'snow_park'), ('leisure', 'snow_park'), ('man_made', 'piste:halfpipe'))
FLAG_KEYS = {'sb:ungroomed', 'sb:gladed', 'sb:park', 'sb:out_of_bounds'}
# Run importance (sb:rank): within each rating, the trunk runs (rank 1) are the longest named in-bounds runs that
# together make up this share of that rating's named in-bounds run length; runs shorter than MINOR_RUN_M are minor
# (rank 3). Ranked per rating since the review of 2026-10-17: one share for the whole resort gave the trunk to the long
# blue cruisers, and short expert runs never had it (8% of Mammoth's expert length, none of Big White's).
TRUNK_SHARE = 0.5
MINOR_RUN_M = 300.0
# The ratings as the style colours a run, the harder first: a named run split equally between two belongs to the harder.
RATINGS = ('expert', 'advanced', 'intermediate', 'easy', 'park', 'unrated')
RATING_OF_DIFFICULTY = {'novice': 'easy', 'easy': 'easy', 'intermediate': 'intermediate', 'advanced': 'advanced',
                        'expert': 'expert', 'freeride': 'expert', 'extreme': 'expert'}
# A lift's end is a station of its own unless a kept station is this close (an OSM station node at the end, or a
# station building's centre beside it).
LIFT_END_STATION_M = 40.0


class InputError(Exception):
    pass


# --- reading ---------------------------------------------------------------------------------------------------

def parse_osm(path):
    """Reads Overpass XML. Returns (nodes, node_tags, ways, relations, osm_base, bounds)."""
    nodes, node_tags, ways, rels = {}, {}, {}, {}
    osm_base, bounds = None, None
    for _, el in ET.iterparse(path, events=('end',)):
        tag = el.tag
        if tag == 'node':
            nid = int(el.get('id'))
            nodes[nid] = (float(el.get('lon')), float(el.get('lat')))
            tags = {t.get('k'): t.get('v') for t in el.findall('tag')}
            if tags:
                node_tags[nid] = tags
            el.clear()
        elif tag == 'way':
            ways[int(el.get('id'))] = {
                'nds': [int(n.get('ref')) for n in el.findall('nd')],
                'tags': {t.get('k'): t.get('v') for t in el.findall('tag')},
            }
            el.clear()
        elif tag == 'relation':
            rels[int(el.get('id'))] = {
                'members': [(m.get('type'), int(m.get('ref')), m.get('role') or '') for m in el.findall('member')],
                'tags': {t.get('k'): t.get('v') for t in el.findall('tag')},
            }
            el.clear()
        elif tag == 'meta' and el.get('osm_base'):
            osm_base = el.get('osm_base')
        elif tag == 'bounds':
            bounds = [float(el.get('minlon')), float(el.get('minlat')), float(el.get('maxlon')), float(el.get('maxlat'))]
        elif tag == 'remark':
            text = (el.text or '').strip()
            if 'error' in text.lower():
                raise InputError(f'the Overpass answer carries an error remark: {text[:200]}')
    if osm_base is None:
        raise InputError('the Overpass answer has no <meta osm_base=...>; refusing data without a timestamp')
    return nodes, node_tags, ways, rels, osm_base, bounds


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


# --- geometry --------------------------------------------------------------------------------------------------

class Projection:
    """Local equirectangular projection in metres around a reference point (enough for a resort-sized box)."""

    def __init__(self, lon0, lat0):
        self.lon0, self.lat0 = lon0, lat0
        self.k = EARTH_RADIUS_M * math.pi / 180.0
        self.kx = self.k * math.cos(math.radians(lat0))

    def __call__(self, lon, lat):
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * self.k


class Polygon:
    """Even-odd point-in-polygon over all rings (outer and inner), with edges bucketed into latitude bands."""

    def __init__(self, rings_xy):
        self.edges = []
        for ring in rings_xy:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                if y1 != y2:
                    self.edges.append((x1, y1, x2, y2))
        if not self.edges:
            raise InputError('the ski-area polygon has no area')
        xs = [p[0] for r in rings_xy for p in r]
        ys = [p[1] for r in rings_xy for p in r]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.nbands = max(1, min(1024, len(self.edges) // 4))
        self.band_h = (self.bbox[3] - self.bbox[1]) / self.nbands or 1.0
        self.bands = [[] for _ in range(self.nbands)]
        for e in self.edges:
            b0, b1 = self._band(min(e[1], e[3])), self._band(max(e[1], e[3]))
            for b in range(b0, b1 + 1):
                self.bands[b].append(e)

    def _band(self, y):
        return min(self.nbands - 1, max(0, int((y - self.bbox[1]) / self.band_h)))

    def contains(self, x, y):
        x0, y0, x1, y1 = self.bbox
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        inside = False
        for ex1, ey1, ex2, ey2 in self.bands[self._band(y)]:
            if (ey1 > y) != (ey2 > y) and x < ex1 + (y - ey1) * (ex2 - ex1) / (ey2 - ey1):
                inside = not inside
        return inside


def line_length(xy):
    return sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(xy, xy[1:]))


def inside_fraction(xy, poly):
    """Share of a polyline's length inside the polygon, sampled every DENSIFY_STEP_M metres."""
    total = inside = 0.0
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg == 0.0:
            continue
        n = max(1, int(math.ceil(seg / DENSIFY_STEP_M)))
        for i in range(n):
            t = (i + 0.5) / n
            if poly.contains(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
                inside += seg / n
        total += seg
    if total == 0.0:
        return (1.0 if xy and poly.contains(*xy[0]) else 0.0), 0.0
    return inside / total, total


def ring_area(xy):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:]))) / 2.0


def point_segment_distance(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def assemble_rings(node_lists):
    """Joins open member ways into closed rings by shared end nodes. Returns node-id rings."""
    segs = [list(n) for n in node_lists if len(n) >= 2]
    rings = []
    while segs:
        cur = segs.pop(0)
        while cur[0] != cur[-1]:
            for i, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur = cur + s[1:]
                elif s[-1] == cur[-1]:
                    cur = cur + s[::-1][1:]
                elif s[-1] == cur[0]:
                    cur = s[:-1] + cur
                elif s[0] == cur[0]:
                    cur = s[::-1][:-1] + cur
                else:
                    continue
                segs.pop(i)
                break
            else:
                raise InputError('a multipolygon ring cannot be closed from its member ways')
        rings.append(cur)
    return rings


# --- text ------------------------------------------------------------------------------------------------------

def glyph_safe(value, ranges):
    """NFC, control characters to spaces, format characters dropped, then only characters in the bundled glyph
    ranges; whitespace collapsed. Returns None for an empty result."""
    if value is None:
        return None
    out = []
    for ch in unicodedata.normalize('NFC', value):
        cat = unicodedata.category(ch)
        if cat == 'Cc':
            out.append(' ')
        elif cat == 'Cf':
            continue
        elif any(lo <= ord(ch) <= hi for lo, hi in ranges):
            out.append(ch)
    text = re.sub(r'\s+', ' ', ''.join(out)).strip()
    return text or None


# --- ranks -----------------------------------------------------------------------------------------------------

def rating_of(difficulty, park):
    """The rating a run is drawn in (build-style.mjs runColour): parks orange whatever their difficulty, else by
    difficulty; anything unrated is 'unrated'."""
    return 'park' if park else RATING_OF_DIFFICULTY.get(difficulty, 'unrated')


def run_ranks(runs, trunk_share=TRUNK_SHARE, minor_m=MINOR_RUN_M):
    """Ranks run lines by importance. `runs` is a list of (name or None, length in metres, out of bounds, rating);
    returns (ranks in the same order, per rating with named in-bounds runs: how many, how many are trunk runs and
    the length of the shortest trunk run).

    A named run is all the ways of that name, whose lengths add up; it belongs to the rating holding most of its
    in-bounds length (equal lengths: the harder rating, in RATINGS order). In each rating, its trunk runs (rank 1) are
    the longest of its named runs with at least one in-bounds way, taken longest first (ties by name) until they make
    up `trunk_share` of the rating's named in-bounds length. Runs shorter than `minor_m` (a named run's total, an
    unnamed way's own length) are rank 3, the others rank 2."""
    totals, inbound, split = {}, {}, {}
    for name, length, oob, rating in runs:
        if rating not in RATINGS:
            raise InputError(f'unknown rating {rating!r}')
        if name:
            totals[name] = totals.get(name, 0.0) + length
            if not oob:
                inbound[name] = inbound.get(name, 0.0) + length
                by = split.setdefault(name, {})
                by[rating] = by.get(rating, 0.0) + length
    home = {n: max(RATINGS, key=lambda g: (split[n].get(g, 0.0), -RATINGS.index(g))) for n in inbound}
    trunk, stats = set(), {}
    for rating in RATINGS:
        names = sorted((n for n in inbound if home[n] == rating), key=lambda n: (-totals[n], n))
        if not names:
            continue
        target = trunk_share * sum(inbound[n] for n in names)
        acc, taken, shortest = 0.0, 0, None
        for name in names:
            if acc >= target:
                break
            trunk.add(name)
            acc += inbound[name]
            taken += 1
            shortest = totals[name]
        stats[rating] = {'named_runs': len(names), 'trunk_runs': taken,
                         'shortest_trunk_run_m': round(shortest) if shortest is not None else None}
    ranks = []
    for name, length, _, _ in runs:
        size = totals[name] if name else length
        ranks.append(1 if name in trunk else 3 if size < minor_m else 2)
    return ranks, stats


# --- overrides -------------------------------------------------------------------------------------------------

ID_RE = re.compile(r'^(node|way|relation)/([1-9][0-9]*)$')


def load_overrides(path, slug, difficulties):
    if path is None or not os.path.exists(path):
        return []
    doc = load_json(path)
    if doc.get('slug') != slug:
        raise InputError(f'{path}: slug {doc.get("slug")!r} does not match {slug!r}')
    entries = doc.get('overrides', [])
    seen = set()
    for i, e in enumerate(entries):
        where = f'{path}: overrides[{i}]'
        if not isinstance(e, dict) or not ID_RE.match(str(e.get('id', ''))):
            raise InputError(f'{where}: id must look like way/123')
        if e['id'] in seen:
            raise InputError(f'{where}: {e["id"]} appears twice')
        seen.add(e['id'])
        if not str(e.get('reason', '')).strip():
            raise InputError(f'{where}: every override needs a reason')
        unknown = set(e) - {'id', 'reason', 'expect', 'set', 'hide'}
        if unknown:
            raise InputError(f'{where}: unknown keys {sorted(unknown)}')
        if e.get('hide') not in (None, True):
            raise InputError(f'{where}: hide must be true when present')
        changes = e.get('set', {})
        if e.get('hide') and changes:
            raise InputError(f'{where}: a hidden element takes no other change')
        if not e.get('hide') and not changes:
            raise InputError(f'{where}: nothing to change (use set or hide)')
        if set(changes) - OVERRIDE_SET_KEYS:
            raise InputError(f'{where}: set may only hold {sorted(OVERRIDE_SET_KEYS)}')
        if 'name' in changes and changes['name'] is not None and not str(changes['name']).strip():
            raise InputError(f'{where}: use "name": null to hide a name')
        if 'difficulty' in changes and changes['difficulty'] not in difficulties:
            raise InputError(f'{where}: difficulty must be one of {difficulties}')
        for k in ('park', 'out_of_bounds'):
            if k in changes and not isinstance(changes[k], bool):
                raise InputError(f'{where}: {k} must be true or false')
        expect = e.get('expect', {})
        if not isinstance(expect, dict) or not all(isinstance(v, (str, type(None))) for v in expect.values()):
            raise InputError(f'{where}: expect maps OSM tag keys to a string, or to null for an absent tag')
    return entries


# --- main ------------------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--resorts', required=True)
    ap.add_argument('--schema', required=True)
    ap.add_argument('--slug', required=True)
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out-osm', required=True)
    ap.add_argument('--out-features', required=True)
    ap.add_argument('--out-report', required=True)
    ap.add_argument('--overrides')
    ap.add_argument('--allow-stale-overrides', action='store_true')
    ap.add_argument('--osm-base', help='data timestamp, when it is not the answer\'s <meta osm_base> (date-pinned query)')
    a = ap.parse_args(argv)
    try:
        return run(a)
    except InputError as e:
        print(f'normalize_osm: {e}', file=sys.stderr)
        return 2


def run(a):
    resorts = load_json(a.resorts)
    schema = load_json(a.schema)
    resort = next((r for r in resorts['resorts'] if r['slug'] == a.slug), None)
    if resort is None:
        raise InputError(f'no resort {a.slug!r} in {a.resorts}')
    ranges = [tuple(r) for r in schema['glyph_ranges']]
    values = schema['values']
    difficulties = values['difficulty']
    keep_types = set(values['piste_type'])
    lift_kinds = set(values['lift_kind'])
    overrides_path = a.overrides or os.path.join(os.path.dirname(os.path.abspath(a.resorts)), 'resorts', f'{a.slug}.overrides.json')
    overrides = load_overrides(overrides_path, a.slug, difficulties)

    nodes, node_tags, ways, rels, osm_base, bounds = parse_osm(a.src)
    if a.osm_base:
        if not re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$', a.osm_base) or a.osm_base > osm_base:
            raise InputError(f'--osm-base {a.osm_base!r} is not a timestamp at or before the answer\'s {osm_base}')
        osm_base = a.osm_base
    w, s, e, n = resort['box']
    proj = Projection((w + e) / 2.0, (s + n) / 2.0)
    report = {
        'slug': a.slug, 'key': resort['key'], 'osm_base': osm_base, 'input_bounds': bounds,
        'kept': {}, 'dropped': {}, 'relation_fills': 0, 'relation_fill_conflicts': [],
        'overrides': {'applied': [], 'stale': []}, 'out_of_bounds': [], 'outside_ski_area_in_bounds': [],
        'names_changed_by_glyph_filter': [], 'difficulty_unknown': 0,
    }

    def drop(reason):
        report['dropped'][reason] = report['dropped'].get(reason, 0) + 1

    # 1. Route relations -> member ways. The first relation to fill a way's piste:type decides it, so routes of a kept
    # type go first: a way shared by a downhill route and a ski-touring or nordic one stays a run, whatever the ids.
    def kept_type(value):
        return any(v.strip().lower() in keep_types for v in (value or '').split(';'))

    filled_from = {}
    for rid in sorted(rels, key=lambda r: (not kept_type(rels[r]['tags'].get('piste:type')), r)):
        rt = rels[rid]['tags']
        rtype = rt.get('piste:type')
        if rt.get('type') not in ('route', 'superroute') or not rtype:
            continue
        rname = rt.get('piste:name') or rt.get('name')
        rref = rt.get('piste:ref') or rt.get('ref')
        for mtype, ref, _role in rels[rid]['members']:
            if mtype != 'way' or ref not in ways:
                continue
            wt = ways[ref]['tags']
            if wt.get('piste:type', rtype) != rtype:
                continue
            got = filled_from.setdefault(ref, {})
            changed = False
            # patrolled too: the out-of-bounds rule (step 4) reads it like piste:grooming.
            for k, v in (('piste:type', rtype), ('piste:difficulty', rt.get('piste:difficulty')),
                         ('piste:grooming', rt.get('piste:grooming')), ('patrolled', rt.get('patrolled'))):
                if v is None:
                    continue
                if k not in wt:
                    wt[k] = v
                    got[k] = rid
                    changed = True
                elif k in got and wt[k] != v:
                    report['relation_fill_conflicts'].append(
                        {'way': ref, 'key': k, 'kept': wt[k], 'from': f'relation/{got[k]}', 'ignored': v, 'ignored_from': f'relation/{rid}'})
            if rname and not (wt.get('piste:name') or wt.get('name')):
                wt['piste:name'] = rname
                got['piste:name'] = rid
                changed = True
            if rref and not (wt.get('piste:ref') or wt.get('ref')):
                wt['piste:ref'] = rref
                got['piste:ref'] = rid
                changed = True
            report['relation_fills'] += 1 if changed else 0

    # 2. Overrides (checked against the tags as filled from relations).
    def element(oid):
        kind, num = oid.split('/')
        num = int(num)
        if kind == 'way':
            return ways.get(num)
        if kind == 'relation':
            return rels.get(num)
        return {'tags': node_tags[num]} if num in node_tags else None

    applied = {}
    for o in overrides:
        el = element(o['id'])
        if el is None:
            report['overrides']['stale'].append({'id': o['id'], 'problem': 'not in the Overpass answer'})
            continue
        mismatch = {k: {'expected': v, 'found': el['tags'].get(k)} for k, v in o.get('expect', {}).items() if el['tags'].get(k) != v}
        if mismatch:
            report['overrides']['stale'].append({'id': o['id'], 'problem': 'expect no longer matches OSM', 'tags': mismatch})
            continue
        applied[o['id']] = o
        report['overrides']['applied'].append({'id': o['id'], 'hide': bool(o.get('hide')), 'set': o.get('set', {}), 'reason': o['reason']})
    if report['overrides']['stale'] and not a.allow_stale_overrides:
        write_json(a.out_report, report)
        for st in report['overrides']['stale']:
            print(f'normalize_osm: stale override {st["id"]}: {st["problem"]} {json.dumps(st.get("tags", {}), ensure_ascii=False)}', file=sys.stderr)
        print('normalize_osm: fix or remove those entries in the overrides file (or pass --allow-stale-overrides to skip them)', file=sys.stderr)
        return 3

    # 3. The ski-area polygon.
    sa_kind, sa_num = resort['ski_area'].split('/')
    sa_num = int(sa_num)
    if sa_kind == 'way':
        sa = ways.get(sa_num)
        if sa is None:
            raise InputError(f'ski area {resort["ski_area"]} is not in the Overpass answer')
        if len(sa['nds']) < 4 or sa['nds'][0] != sa['nds'][-1]:
            raise InputError(f'ski area {resort["ski_area"]} is not a closed way')
        outer_ids, inner_ids = [sa['nds']], []
    elif sa_kind == 'relation':
        sa = rels.get(sa_num)
        if sa is None:
            raise InputError(f'ski area {resort["ski_area"]} is not in the Overpass answer')
        members = [(ways[ref]['nds'], role) for t, ref, role in sa['members'] if t == 'way' and ref in ways]
        outer_ids = assemble_rings([nds for nds, role in members if role in ('outer', '')])
        inner_ids = assemble_rings([nds for nds, role in members if role == 'inner'])
    else:
        raise InputError(f'ski area id must be a way or a relation: {resort["ski_area"]}')
    missing = [nid for ring in outer_ids + inner_ids for nid in ring if nid not in nodes]
    if missing:
        raise InputError(f'ski area {resort["ski_area"]} lacks {len(missing)} node(s) in the Overpass answer')
    sa_rings_ll = [[nodes[nid] for nid in ring] for ring in outer_ids + inner_ids]
    sa_poly = Polygon([[proj(*p) for p in ring] for ring in sa_rings_ll])
    sa_area_km2 = (sum(ring_area([proj(*p) for p in [nodes[i] for i in r]]) for r in outer_ids)
                   - sum(ring_area([proj(*p) for p in [nodes[i] for i in r]]) for r in inner_ids)) / 1e6
    report['ski_area'] = {'id': resort['ski_area'], 'name': glyph_safe(sa['tags'].get('name'), ranges), 'area_km2': round(sa_area_km2, 2)}

    def safe(value, oid, field):
        out = glyph_safe(value, ranges)
        if value is not None and out != value.strip():
            report['names_changed_by_glyph_filter'].append({'id': oid, 'field': field, 'osm': value, 'map': out})
        return out

    kept = []   # (osm type, id, sb tags, geometry for GeoJSON, extra props)

    def way_coords(wid):
        nds = ways[wid]['nds']
        if any(nid not in nodes for nid in nds):
            return None
        return [nodes[nid] for nid in nds]

    def is_closed(wid):
        nds = ways[wid]['nds']
        return len(nds) >= 4 and nds[0] == nds[-1]

    # 4. Runs.
    def piste_type(t):
        if 'piste:type' in t:
            types = [v.strip().lower() for v in t['piste:type'].split(';')]
            for v in types:
                if v in keep_types:
                    return v, None
            return None, types[0]
        if any(t.get(k) == v for k, v in PARK_TAGS):
            return 'snow_park', None
        return None, None

    run_lines = []   # indexes in kept of the run lines, for their ranks
    candidates = [('way', wid, ways[wid]['tags']) for wid in sorted(ways)]
    candidates += [('relation', rid, rels[rid]['tags']) for rid in sorted(rels) if rels[rid]['tags'].get('type') == 'multipolygon']
    for otype, oid, t in candidates:
        if t.get('aerialway') in lift_kinds or (otype == sa_kind and oid == sa_num):
            continue
        ptype, other = piste_type(t)
        if ptype is None:
            if other is not None:
                drop(f'piste_type:{other}')
            continue
        key = f'{otype}/{oid}'
        o = applied.get(key)
        if o and o.get('hide'):
            drop('hidden_by_override')
            continue
        changes = o.get('set', {}) if o else {}
        if otype == 'way':
            coords = way_coords(oid)
            if coords is None or len(coords) < 2:
                drop('piste_without_geometry')
                continue
            area = is_closed(oid) and t.get('area') == 'yes'
            rings_ll = [coords] if area else None
            n_outer = 1
        else:
            try:
                members = [(ways[ref]['nds'], role) for mt, ref, role in rels[oid]['members'] if mt == 'way' and ref in ways]
                outer_r = assemble_rings([nds for nds, role in members if role in ('outer', '')])
                inner_r = assemble_rings([nds for nds, role in members if role == 'inner'])
            except InputError:
                drop('piste_area_unclosed')
                continue
            if not outer_r or any(nid not in nodes for r in outer_r + inner_r for nid in r):
                drop('piste_without_geometry')
                continue
            rings_ll = [[nodes[nid] for nid in r] for r in outer_r + inner_r]
            n_outer = len(outer_r)
            area = True
            coords = None
        difficulty = (t.get('piste:difficulty') or '').strip().lower()
        if difficulty not in difficulties:
            difficulty = 'unknown'
        if 'difficulty' in changes:
            difficulty = changes['difficulty']
        if difficulty == 'unknown':
            report['difficulty_unknown'] += 1
        grooming = {g.strip().lower() for g in (t.get('piste:grooming') or '').split(';') if g.strip()}
        gladed = t.get('gladed') == 'yes' or t.get('piste:gladed') == 'yes'
        park = ptype == 'snow_park' or any(t.get(k) == v for k, v in PARK_TAGS)
        if 'park' in changes:
            park = changes['park']
        ungroomed = bool(grooming & UNGROOMED_GROOMING) or gladed or difficulty in UNGROOMED_DIFFICULTY
        raw_name = t.get('piste:name') or t.get('name')
        name = safe(raw_name, key, 'name')
        if 'name' in changes:
            name = glyph_safe(changes['name'], ranges)
        ref = safe(t.get('piste:ref') or t.get('ref'), key, 'ref')
        if area:
            outline = [[proj(*p) for p in ring] for ring in rings_ll]
            fracs = [inside_fraction(r, sa_poly) for r in outline[:n_outer]]
            total = sum(L for _, L in fracs)
            in_frac = sum(f * L for f, L in fracs) / total if total else 0.0
            size = {'area_m2': round(sum(ring_area(r) for r in outline[:n_outer]) - sum(ring_area(r) for r in outline[n_outer:]))}
        else:
            in_frac, length = inside_fraction([proj(*p) for p in coords], sa_poly)
            size = {'length_m': round(length)}
        backcountry = 'backcountry' in grooming or t.get('patrolled') == 'no'
        oob = backcountry and in_frac < OOB_MAX_INSIDE_FRACTION
        if 'out_of_bounds' in changes:
            oob = changes['out_of_bounds']
        sb = {'sb:layer': 'piste_area' if area else 'piste', 'sb:type': ptype, 'sb:difficulty': difficulty}
        for flag, on in (('sb:ungroomed', ungroomed), ('sb:gladed', gladed), ('sb:park', park), ('sb:out_of_bounds', oob)):
            if on:
                sb[flag] = 'yes'
        if name:
            sb['sb:name'] = name
        if ref:
            sb['sb:ref'] = ref
        info = {'id': key, 'name': name, 'difficulty': difficulty, 'grooming': ';'.join(sorted(grooming)) or None,
                'patrolled': t.get('patrolled'), 'in_frac': round(in_frac, 3), **size}
        if oob:
            report['out_of_bounds'].append(info)
        elif in_frac < OOB_MAX_INSIDE_FRACTION:
            report['outside_ski_area_in_bounds'].append(info)
        geom = ({'type': 'Polygon', 'coordinates': rings_ll} if area else {'type': 'LineString', 'coordinates': coords})
        kept.append((otype, oid, sb, geom, {'out_of_bounds': oob, 'in_frac': round(in_frac, 3), **size}))
        if not area:
            run_lines.append(len(kept) - 1)

    # Ranks: the trunk runs, minor runs and the others (the style draws the overview zooms by rank).
    ranks, by_rating = run_ranks([(kept[i][2].get('sb:name'), kept[i][4]['length_m'], kept[i][4]['out_of_bounds'],
                                   rating_of(kept[i][2]['sb:difficulty'], kept[i][2].get('sb:park') == 'yes'))
                                  for i in run_lines])
    for i, rank in zip(run_lines, ranks):
        kept[i][2]['sb:rank'] = str(rank)
    report['ranks'] = {'trunk_share': TRUNK_SHARE, 'trunk_per': 'rating', 'minor_run_m': MINOR_RUN_M,
                       'ratings': by_rating, 'runs': {str(r): ranks.count(r) for r in (1, 2, 3)}}

    # 5. Lifts.
    lift_segments = []
    lift_ends = set()   # node ids of the kept lifts' ends
    for wid in sorted(ways):
        t = ways[wid]['tags']
        kind = t.get('aerialway')
        if kind is None or kind in ('station', 'pylon'):
            continue
        if kind not in lift_kinds:
            drop(f'aerialway:{kind}')
            continue
        key = f'way/{wid}'
        o = applied.get(key)
        if o and o.get('hide'):
            drop('hidden_by_override')
            continue
        coords = way_coords(wid)
        if coords is None or len(coords) < 2:
            drop('lift_without_geometry')
            continue
        sb = {'sb:layer': 'lift', 'sb:kind': kind}
        name = safe(t.get('name'), key, 'name')
        if o and 'name' in o.get('set', {}):
            name = glyph_safe(o['set']['name'], ranges)
        if name:
            sb['sb:name'] = name
        ref = safe(t.get('ref'), key, 'ref')
        if ref:
            sb['sb:ref'] = ref
        occ = (t.get('aerialway:occupancy') or '').strip()
        if occ.isdigit() and 0 < int(occ) < 1000:
            sb['sb:occupancy'] = str(int(occ))
        xy = [proj(*p) for p in coords]
        lift_segments += list(zip(xy, xy[1:]))
        lift_ends.update((ways[wid]['nds'][0], ways[wid]['nds'][-1]))
        kept.append(('way', wid, sb, {'type': 'LineString', 'coordinates': coords}, {'length_m': round(line_length(xy))}))

    # 6. Lift stations near a kept lift.
    def near_lift(lonlat):
        p = proj(*lonlat)
        return any(point_segment_distance(p, a2, b2) <= STATION_MAX_DISTANCE_M for a2, b2 in lift_segments)

    stations = [('node', nid, node_tags[nid], nodes[nid]) for nid in sorted(node_tags) if node_tags[nid].get('aerialway') == 'station']
    for wid in sorted(ways):
        if ways[wid]['tags'].get('aerialway') == 'station':
            coords = way_coords(wid)
            if coords is None or not is_closed(wid):
                drop('station_not_a_closed_way')
                continue
            ring = coords[:-1]
            stations.append(('way', wid, ways[wid]['tags'], (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))))
    for otype, oid, t, centre in stations:
        key = f'{otype}/{oid}'
        o = applied.get(key)
        if o and o.get('hide'):
            drop('hidden_by_override')
            continue
        if not near_lift(centre):
            drop('station_far_from_lifts')
            continue
        sb = {'sb:layer': 'lift_station'}
        name = safe(t.get('name'), key, 'name')
        if o and 'name' in o.get('set', {}):
            name = glyph_safe(o['set']['name'], ranges)
        if name:
            sb['sb:name'] = name
        geom = {'type': 'Point', 'coordinates': list(centre)}
        kept.append((otype, oid, sb, geom, {}))

    # The two ends of every kept lift are its terminals: a station each, unless a kept station is already within
    # LIFT_END_STATION_M (OpenStreetMap maps many terminals only as the lift's end node, or not at all).
    station_xy = [proj(*k[3]['coordinates']) for k in kept if k[2]['sb:layer'] == 'lift_station']
    station_nodes = {k[1] for k in kept if k[0] == 'node' and k[2]['sb:layer'] == 'lift_station'}
    report['lift_end_stations'] = 0
    for nid in sorted(lift_ends):
        p = proj(*nodes[nid])
        if nid in station_nodes or any(math.hypot(p[0] - q[0], p[1] - q[1]) <= LIFT_END_STATION_M for q in station_xy):
            continue
        kept.append(('node', nid, {'sb:layer': 'lift_station'}, {'type': 'Point', 'coordinates': list(nodes[nid])}, {'lift_end': True}))
        station_xy.append(p)
        report['lift_end_stations'] += 1

    # 7. The ski area itself.
    sb = {'sb:layer': 'ski_area'}
    if report['ski_area']['name']:
        sb['sb:name'] = report['ski_area']['name']
    kept.append((sa_kind, sa_num, sb, {'type': 'Polygon', 'coordinates': sa_rings_ll}, {'area_m2': round(sa_area_km2 * 1e6)}))

    for _, _, sbt, _, _ in kept:
        report['kept'][sbt['sb:layer']] = report['kept'].get(sbt['sb:layer'], 0) + 1
    report['dropped'] = dict(sorted(report['dropped'].items()))
    report['out_of_bounds'].sort(key=lambda r: r['id'])
    report['outside_ski_area_in_bounds'].sort(key=lambda r: r['id'])

    write_osm(a.out_osm, kept, nodes, ways, rels, bounds, sa_kind, sa_num)
    write_json(a.out_features, features(kept))
    write_json(a.out_report, report)
    k = report['kept']
    print(f'{a.slug}: osm_base {osm_base}; kept {k.get("piste", 0)} runs, {k.get("piste_area", 0)} run areas, '
          f'{k.get("lift", 0)} lifts, {k.get("lift_station", 0)} stations; {len(report["out_of_bounds"])} out of bounds; '
          f'{len(report["overrides"]["applied"])} overrides applied; dropped {sum(report["dropped"].values())}')
    return 0


def features(kept):
    def rnd(c):
        if isinstance(c, (list, tuple)) and c and isinstance(c[0], (int, float)):
            return [round(c[0], 7), round(c[1], 7)]
        return [rnd(x) for x in c]

    out = []
    for otype, oid, sb, geom, extra in kept:
        props = {'osm': f'{otype}/{oid}', 'layer': sb['sb:layer']}
        for k, v in sb.items():
            if k == 'sb:layer':
                continue
            if k in FLAG_KEYS:
                props[k[3:]] = True
            elif k in ('sb:occupancy', 'sb:rank'):
                props[k[3:]] = int(v)
            else:
                props[k[3:]] = v
        props.update(extra)
        out.append({'type': 'Feature', 'geometry': {'type': geom['type'], 'coordinates': rnd(geom['coordinates'])}, 'properties': props})
    return {'type': 'FeatureCollection', 'features': out}


def write_osm(path, kept, nodes, ways, rels, bounds, sa_kind, sa_num):
    """Writes only the kept elements, with their sb:* tags, plus the untagged member ways and nodes they need."""
    out_nodes, out_ways, out_rels = {}, {}, {}
    for otype, oid, sb, _, _ in kept:
        if otype == 'node':
            out_nodes[oid] = sb
        elif otype == 'way':
            out_ways[oid] = sb
        else:
            tags = dict(sb)
            tags['type'] = 'multipolygon'
            out_rels[oid] = tags
    for rid in out_rels:
        for mt, ref, _ in rels[rid]['members']:
            if mt == 'way' and ref in ways:
                out_ways.setdefault(ref, {})
    for wid in out_ways:
        for nid in ways[wid]['nds']:
            out_nodes.setdefault(nid, {})

    def tags_xml(tags, indent):
        return ''.join(f'{indent}<tag k={quoteattr(k)} v={quoteattr(v)}/>\n' for k, v in sorted(tags.items()))

    parts = ["<?xml version='1.0' encoding='UTF-8'?>\n", '<osm version="0.6" generator="snowbuddy normalize_osm.py">\n']
    if bounds:
        parts.append(f'  <bounds minlat="{bounds[1]:.7f}" minlon="{bounds[0]:.7f}" maxlat="{bounds[3]:.7f}" maxlon="{bounds[2]:.7f}"/>\n')
    for nid in sorted(out_nodes):
        lon, lat = nodes[nid]
        tags = out_nodes[nid]
        if tags:
            parts.append(f'  <node id="{nid}" lat="{lat:.7f}" lon="{lon:.7f}">\n{tags_xml(tags, "    ")}  </node>\n')
        else:
            parts.append(f'  <node id="{nid}" lat="{lat:.7f}" lon="{lon:.7f}"/>\n')
    for wid in sorted(out_ways):
        nds = ''.join(f'    <nd ref="{nid}"/>\n' for nid in ways[wid]['nds'])
        parts.append(f'  <way id="{wid}">\n{nds}{tags_xml(out_ways[wid], "    ")}  </way>\n')
    for rid in sorted(out_rels):
        mem = ''.join(f'    <member type="way" ref="{ref}" role={quoteattr(role)}/>\n'
                      for mt, ref, role in rels[rid]['members'] if mt == 'way' and ref in ways)
        parts.append(f'  <relation id="{rid}">\n{mem}{tags_xml(out_rels[rid], "    ")}  </relation>\n')
    parts.append('</osm>\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))


def write_json(path, doc):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')


if __name__ == '__main__':
    sys.exit(main())

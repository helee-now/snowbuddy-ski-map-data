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
       ski_area           the resort's own polygon, picked by its OSM id. A resort of several mountains on one map
                          lists one landuse=winter_sports polygon per mountain (`ski_area` as a list); they must not
                          overlap (touching is fine), their union is the ski area of every inside test, and they make
                          one feature named after the resort: a multipolygon of the union's rings, each written as one
                          closed way (a border two of them share left out, rings that meet at a node kept apart).
                          Or, for a resort with no such polygon in OpenStreetMap (`ski_area` "derived", owner decision
                          2026-10-30), the kept lifts and runs buffered by `ski_area_buffer_m` (100 m by default),
                          unioned, every hole filled, written the same way (derive_ski_area; step 5a);
     A lift, run or run area of another resort that resorts.json lists in `neighbours` (owner decision 2026-10-21:
     each map draws only its own resort) is left out, before the stations and the ranks, and the stations of its lifts
     go with it. A feature is the resort's when the resort's polygon (the union) holds at least half of its length (a
     run area: of its outline; a stretch along a polygon's edge lies in it), else the listed neighbour's that holds the
     most of it, at least half; else it belongs to the nearest polygon within 250 m (ties to the larger share, then to
     the resort), else to none (kept). Each neighbour must be in the answer as a landuse=winter_sports area with the
     OSM name resorts.json gives, or the build stops, as for a stale override;
  4. ranks every run line by importance (sb:rank, for the style's overview zooms): 1 for the trunk runs, in each
     rating the style draws in its own colour (easy, intermediate, advanced, expert, park, unrated) the longest named
     runs that together make up half of that rating's named in-bounds run length; 3 for runs under 300 m (a named
     run's length summed over all its ways, an unnamed way's own length); 2 for the others. With several mountains a
     named run is the ways of that name on one mountain (the listed polygon owning each way by the rule above, else
     the nearest one);
  5. reduces every string to the glyph ranges the app bundles (ADR-015).

orient.py then turns runs downhill and lifts uphill from the elevation model (ski.sh runs it after the contours).

Outputs: an OSM XML file whose elements carry only `sb:*` tags (osmium turns it into the PBF that
ski-overlay.yml reads through Planetiler), a GeoJSON file of the kept features (read by coverage.py) and a JSON
report (with, per listed neighbour, the ids of what was left out). No OSM user names, user ids or changesets are
written.

Usage:
  python3 -I normalize_osm.py --resorts resorts.json --schema pack-schema.json --slug big-white \
      --in overpass.osm --out-osm normalized.osm --out-features features.geojson --out-report normalize.json \
      [--overrides resorts/big-white.overrides.json] [--allow-stale-overrides] [--osm-base TIMESTAMP]

--osm-base gives the data timestamp when the answer's own <meta osm_base> is not it: a date-pinned Overpass query
([date:"..."]) still reports the server's current time there (packlib.py osm-info decides, build-pack.sh passes it).

Exit codes: 0 done, 2 bad input or configuration (among them a listed ski area or neighbour missing from the answer,
not a landuse=winter_sports area, overlapping another listed ski area, or a neighbour whose OSM name changed),
3 stale overrides.
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
# A resort of several mountains on one map lists each mountain's polygon in `ski_area`; their union is the ski area of
# every inside test. They are written as ONE ski_area feature, as one id is: in the OSM file a multipolygon relation of
# the union's rings, which needs an id of its own. Planetiler refuses negative ids and writes the id into the tiles
# (id * 10 + 3), so it is this one, far above any OSM relation id (about 2 * 10^7 in 2026) and small enough that the
# tile's feature id stays below 2^53 for JavaScript readers. Each ring is one closed, untagged way of its own, with the
# ids from this one up (OSM way ids are about 1.5 * 10^9). Not the listed polygons' own ways: Planetiler keeps one copy
# of a way listed twice (a border two mountains share, or a mountain filling another's hole) and joins open ways into
# rings at their end nodes, one way per node, so where four ends meet (two mountains touching at a corner) a ring is
# lost. Made-up answers drawn with the real profile (2026-10-22) gave no ski area, a mountain drawn as a hole, and one
# mountain of two.
SKI_AREA_RELATION_ID = 100_000_000_000_000
# Neighbours (resorts.json `neighbours`, owner decision 2026-10-21: each map draws only its own resort). A lift, run line
# or run area is the resort's when the resort's polygon (the union) holds at least this share of its length (a run area:
# of its outline), else the listed neighbour's holding the most of it, at least this share; a stretch lying on a
# polygon's edge counts as inside it, so a run along a border the resort shares with a neighbour stays, whichever side
# the neighbour is on. Otherwise it belongs to the nearest of them within NEIGHBOUR_NEAR_M (0 when touching); else to
# none, and it is kept as before. A listed neighbour's are left out, with the stations of its lifts. The same rule,
# without the distance limit, gives each run line its mountain for the ranks when several polygons are listed.
OWNER_MIN_SHARE = 0.5
NEIGHBOUR_NEAR_M = 250.0
# A ski area derived from the resort's own lifts and runs (resorts.json `ski_area: "derived"`, owner decision
# 2026-10-30, for a resort with no landuse=winter_sports polygon in OpenStreetMap): the kept lifts and downhill runs
# (lines, and run areas' outlines), after the overrides and the neighbour rule, each buffered by `ski_area_buffer_m`
# (DERIVED_BUFFER_M when absent), unioned, every hole filled, groups whose buffers do not touch (farther apart than
# twice the buffer) as parts of their own, the outline simplified at DERIVED_SIMPLIFY_M. The buffer's edge is traced
# on a DERIVED_GRID_M grid (derive_ski_area). Written as the union of several mountains is: one ski_area relation
# (SKI_AREA_RELATION_ID) of closed untagged ways, their nodes with the ids right after the answer's highest node id:
# Planetiler's node-location index is a sparse array whose cost grows with the id range, so ids near
# SKI_AREA_RELATION_ID overflow it ("Index -1656 out of bounds") and ids at 5 * 10^10, four times OpenStreetMap's, ran
# its 2 GB heap out (both seen 2026-10-30), while ids just past the answer's own cost nothing. The tiles never carry a
# node id (the rings' ways are untagged; the relation is the feature), so the ski file's bytes do not depend on them.
DERIVED_BUFFER_M = 100.0
DERIVED_BUFFER_RANGE_M = (10.0, 1000.0)
DERIVED_GRID_M = 10.0
DERIVED_SIMPLIFY_M = 5.0


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
    """Even-odd point-in-polygon over all rings (outer and inner), with edges bucketed into latitude bands. The rings
    of several polygons that do not overlap make their union (a resort of several mountains)."""

    def __init__(self, rings_xy):
        self.rings = rings_xy
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
        self._grid = None

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

    def covers(self, x, y, eps=1e-3):
        """Inside, or on the boundary (within eps metres of it). `contains` counts a point on an edge as inside only the
        polygon east of it (north of it, for a horizontal edge), so two polygons that share an edge never both hold a
        line drawn along it; this does."""
        x0, y0, x1, y1 = self.bbox
        if x < x0 - eps or x > x1 + eps or y < y0 - eps or y > y1 + eps:
            return False
        return self.contains(x, y) or any(point_segment_distance((x, y), a, b) <= eps
                                          for a, b in self.grid().near((x - eps, y - eps, x + eps, y + eps)))

    # The boundary's segments (horizontal ones included, which the ray test above skips), in a grid, for distances
    # (the neighbour rule) and the overlap test of a resort's listed polygons.
    def grid(self):
        if self._grid is None:
            self._grid = SegmentGrid([(a, b) for ring in self.rings for a, b in zip(ring, ring[1:]) if a != b])
        return self._grid

    def distance_to(self, lines, limit):
        """Shortest distance in metres from the polylines to the polygon's boundary, 0 when they touch or cross it;
        math.inf when it is over `limit` (math.inf: no limit). (A line wholly inside is 0 by the caller's share test,
        not here.)"""
        if math.isinf(limit):
            for step in (250.0, 1000.0, 4000.0, 16000.0, 64000.0):
                d = self.distance_to(lines, step)
                if d <= step:
                    return d
            return min((segment_distance(p1, p2, q1, q2) for xy in lines for p1, p2 in zip(xy, xy[1:])
                        for q1, q2 in self.grid().segments), default=math.inf)
        best = math.inf
        grid = self.grid()
        for xy in lines:
            for p1, p2 in zip(xy, xy[1:]):
                box = (min(p1[0], p2[0]) - limit, min(p1[1], p2[1]) - limit, max(p1[0], p2[0]) + limit, max(p1[1], p2[1]) + limit)
                for q1, q2 in grid.near(box):
                    d = segment_distance(p1, p2, q1, q2)
                    if d < best:
                        best = d
                        if best == 0.0:
                            return 0.0
        return best if best <= limit else math.inf

    def strictly_contains(self, x, y, eps=1e-3):
        """Inside and more than eps metres from the boundary."""
        if not self.contains(x, y):
            return False
        return all(point_segment_distance((x, y), a, b) > eps for a, b in self.grid().near((x - eps, y - eps, x + eps, y + eps)))

    def inner_point(self):
        """A point strictly inside the polygon: the middle of the widest stretch inside it along one of a few
        horizontal lines through its bounding box (at odd fractions of its height, so they seldom meet a vertex); None
        when no such middle is strictly inside."""
        x0, y0, x1, y1 = self.bbox
        stretches = []
        for f in (0.5003, 0.3137, 0.6871, 0.1709, 0.8297):
            y = y0 + (y1 - y0) * f
            xs = sorted(ex1 + (y - ey1) * (ex2 - ex1) / (ey2 - ey1)
                        for ex1, ey1, ex2, ey2 in self.edges if (ey1 > y) != (ey2 > y))
            stretches += [(b - a, ((a + b) / 2.0, y)) for a, b in zip(xs[0::2], xs[1::2]) if b > a]
        for _, p in sorted(stretches, key=lambda s: -s[0]):
            if self.strictly_contains(*p):
                return p
        return None


class SegmentGrid:
    """Segments bucketed into square cells, to find the ones near a box."""

    def __init__(self, segments, cell=250.0):
        self.segments = segments
        self.cell = cell
        self.cells = {}
        for i, (a, b) in enumerate(segments):
            for key in self._keys((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))):
                self.cells.setdefault(key, []).append(i)

    def _range(self, box):
        c = self.cell
        return (int(math.floor(box[0] / c)), int(math.floor(box[2] / c)), int(math.floor(box[1] / c)), int(math.floor(box[3] / c)))

    def _keys(self, box):
        ix0, ix1, iy0, iy1 = self._range(box)
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                yield ix, iy

    def near(self, box):
        """The segments in the cells the box touches (a superset of those within it)."""
        ix0, ix1, iy0, iy1 = self._range(box)
        if (ix1 - ix0 + 1) * (iy1 - iy0 + 1) > len(self.cells):
            # A box wider than the segments' cells: walk the filled cells instead of the empty ones.
            keys = [k for k in self.cells if ix0 <= k[0] <= ix1 and iy0 <= k[1] <= iy1]
        else:
            keys = self._keys(box)
        seen = set()
        for key in keys:
            for i in self.cells.get(key, ()):
                if i not in seen:
                    seen.add(i)
                    yield self.segments[i]


def orient2d(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(p1, p2, q1, q2):
    """The two segments cross at one point inside both: not at an end of either, not along a shared stretch."""
    d1, d2 = orient2d(q1, q2, p1), orient2d(q1, q2, p2)
    d3, d4 = orient2d(p1, p2, q1), orient2d(p1, p2, q2)
    return ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4))


def segment_distance(p1, p2, q1, q2):
    """Distance between two segments: 0 when they cross or touch."""
    if segments_cross(p1, p2, q1, q2):
        return 0.0
    return min(point_segment_distance(p1, q1, q2), point_segment_distance(p2, q1, q2),
               point_segment_distance(q1, p1, p2), point_segment_distance(q2, p1, p2))


def polygons_overlap(a, b):
    """Whether two polygons (Polygon objects) share any area. Touching along an edge or at a point is not an overlap.
    Their boundaries cross, or a vertex, an edge's middle or an inner point of one lies strictly inside the other."""
    if a.bbox[2] <= b.bbox[0] or b.bbox[2] <= a.bbox[0] or a.bbox[3] <= b.bbox[1] or b.bbox[3] <= a.bbox[1]:
        return False
    grid = b.grid()
    for p1, p2 in a.grid().segments:
        box = (min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))
        if any(segments_cross(p1, p2, q1, q2) for q1, q2 in grid.near(box)):
            return True
    for one, other in ((a, b), (b, a)):
        probes = [p for p1, p2 in one.grid().segments for p in (p1, ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0))]
        inner = one.inner_point()
        if inner:
            probes.append(inner)
        if any(other.strictly_contains(*p) for p in probes):
            return True
    return False


def line_length(xy):
    return sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(xy, xy[1:]))


def inside_fraction(xy, poly, closed=False):
    """Share of a polyline's length inside the polygon, sampled every DENSIFY_STEP_M metres; closed: a sample on its
    boundary counts as inside (Polygon.covers)."""
    test = poly.covers if closed else poly.contains
    total = inside = 0.0
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg == 0.0:
            continue
        n = max(1, int(math.ceil(seg / DENSIFY_STEP_M)))
        for i in range(n):
            t = (i + 0.5) / n
            if test(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t):
                inside += seg / n
        total += seg
    if total == 0.0:
        return (1.0 if xy and test(*xy[0]) else 0.0), 0.0
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


def union_rings(rings):
    """The outline of the union of polygons that share no area, from all their node-id rings (outer and inner, each
    closed: its first node repeated at the end). A stretch between two nodes that an even number of the rings use is
    inside the union, or not on it at all, and is left out: a border two of the polygons share, or a ring that fills
    another one's hole. What is left is walked into simple rings, each node at most once in each, so rings that meet at
    a node (two mountains touching at a corner) come out apart. The even-odd area is that of the rings given.

    Returns (the rings, closed, in the order of their first stretch in `rings`; the stretches left out, as node-id
    pairs)."""
    count, order = {}, []
    for ring in rings:
        for u, v in zip(ring, ring[1:]):
            if u == v:
                continue
            key = (u, v) if u < v else (v, u)
            if key not in count:
                count[key] = 0
                order.append(key)
            count[key] += 1
    edges = [key for key in order if count[key] % 2]
    ends = {}
    for i, (u, v) in enumerate(edges):
        ends.setdefault(u, []).append(i)
        ends.setdefault(v, []).append(i)
    used = [False] * len(edges)
    out = []
    for first, (u0, v0) in enumerate(edges):
        if used[first]:
            continue
        used[first] = True
        path, at = [u0, v0], {u0: 0, v0: 1}
        while len(path) > 1:
            here = path[-1]
            # Every node has an even number of stretches left (each ring passes a node in and out), so the walk goes
            # on until it is back at a node it passed: that loop is one ring.
            j = next((j for j in ends[here] if not used[j]), None)
            if j is None:
                raise InputError('the outline of the listed ski areas does not close')
            used[j] = True
            there = edges[j][1] if edges[j][0] == here else edges[j][0]
            if there in at:
                k = at[there]
                out.append(path[k:] + [there])
                for nid in path[k + 1:]:
                    del at[nid]
                del path[k + 1:]
            else:
                at[there] = len(path)
                path.append(there)
    return out, [key for key in order if not count[key] % 2]


def ring_contains(xy, x, y):
    """Even-odd point-in-ring for one closed ring of projected points (the ray test of Polygon.contains)."""
    inside = False
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def ring_roles(rings_xy, eps=1e-3):
    """'outer' or 'inner' for each of the union's rings (projected, closed): inner when an odd number of the others
    hold it. The rings never cross, so one point of a ring that is not on the other one (a node, else the middle of a
    stretch; more than eps metres from it) tells. (Planetiler reads no roles, it nests the rings itself; they are
    written for any other reader.)"""
    roles = []
    for i, xy in enumerate(rings_xy):
        probes = [p for a, b in zip(xy, xy[1:]) for p in (a, ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))]
        depth = 0
        for j, other in enumerate(rings_xy):
            if j == i:
                continue
            stretches = list(zip(other, other[1:]))
            p = next((p for p in probes if all(point_segment_distance(p, a, b) > eps for a, b in stretches)), None)
            depth += p is not None and ring_contains(other, *p)
        roles.append('inner' if depth % 2 else 'outer')
    return roles


# --- a ski area derived from the lifts and runs (resorts.json ski_area "derived") -------------------------------

def simplify_ring(xy, tolerance):
    """Douglas-Peucker on a closed ring (first point repeated at the end): the ring is cut at its first point and at
    the point farthest from it, each half simplified, so the two anchors always stay. Returns a closed ring."""
    def dp(pts):
        if len(pts) <= 2:
            return list(pts)
        a, b = pts[0], pts[-1]
        far, at = -1.0, 0
        for i in range(1, len(pts) - 1):
            d = point_segment_distance(pts[i], a, b)
            if d > far:
                far, at = d, i
        if far <= tolerance:
            return [a, b]
        return dp(pts[:at + 1])[:-1] + dp(pts[at:])
    pts = xy[:-1]
    if len(pts) < 3:
        return list(xy)
    far = max(range(1, len(pts)), key=lambda i: (math.hypot(pts[i][0] - pts[0][0], pts[i][1] - pts[0][1]), -i))
    out = dp(pts[:far + 1])[:-1] + dp(pts[far:] + [pts[0]])
    return out


def derive_ski_area(lines, buffer_m, grid_m=DERIVED_GRID_M, simplify_m=DERIVED_SIMPLIFY_M):
    """The outline of the lifts and runs buffered by `buffer_m` metres (projected polylines), with every hole filled:
    the ski area of a resort that has no landuse=winter_sports polygon in OpenStreetMap (owner decision 2026-10-30).

    The distance to the nearest line is exact at the nodes of a `grid_m` grid (each segment visits only the nodes
    within reach of it), so the buffer's edge is the `buffer_m` isoline of that field; marching squares with the
    crossings interpolated along the grid's edges traces it to about grid_m^2 / (8 buffer_m) (0.1 m for 10 m and
    100 m), with a crease where two buffers meet. Nodes outside the buffer that the grid's border cannot reach are
    holes (a loop of runs around a wood) and are filled before the tracing, so every ring is an outer ring; groups of
    lines whose buffers do not touch give rings of their own. Each ring is then simplified (Douglas-Peucker,
    `simplify_m`). Plain Python on plain floats in a fixed order, so the same lines give the same rings, byte for byte.

    Returns the rings, closed, counter-clockwise, in the order of their first crossing on the grid."""
    pts = [p for xy in lines for p in xy]
    if not pts:
        return []
    h, r = float(grid_m), float(buffer_m)
    reach = r + 2.0 * h
    x0 = math.floor((min(p[0] for p in pts) - reach) / h) * h
    y0 = math.floor((min(p[1] for p in pts) - reach) / h) * h
    nx = int(math.ceil((max(p[0] for p in pts) + reach - x0) / h)) + 1
    ny = int(math.ceil((max(p[1] for p in pts) + reach - y0) / h)) + 1
    inf = math.inf
    dist = [inf] * (nx * ny)
    span = r + h
    for xy in lines:
        for (ax, ay), (bx, by) in zip(xy, xy[1:]):
            dx, dy = bx - ax, by - ay
            dd = dx * dx + dy * dy
            i0 = max(0, int((min(ax, bx) - span - x0) / h))
            i1 = min(nx - 1, int((max(ax, bx) + span - x0) / h) + 1)
            j0 = max(0, int((min(ay, by) - span - y0) / h))
            j1 = min(ny - 1, int((max(ay, by) + span - y0) / h) + 1)
            for j in range(j0, j1 + 1):
                py = y0 + j * h
                row = j * nx
                for i in range(i0, i1 + 1):
                    px = x0 + i * h
                    if dd == 0.0:
                        d = math.hypot(px - ax, py - ay)
                    else:
                        t = ((px - ax) * dx + (py - ay) * dy) / dd
                        t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
                        d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
                    if d < dist[row + i]:
                        dist[row + i] = d
    # Holes: the outside is what the border reaches through nodes beyond the buffer; the rest of the outside is filled.
    seen = bytearray(nx * ny)
    stack = []
    for i in range(nx):
        stack += [i, (ny - 1) * nx + i]
    for j in range(1, ny - 1):
        stack += [j * nx, j * nx + nx - 1]
    while stack:
        k = stack.pop()
        if seen[k] or dist[k] <= r:
            continue
        seen[k] = 1
        i, j = k % nx, k // nx
        if i > 0:
            stack.append(k - 1)
        if i < nx - 1:
            stack.append(k + 1)
        if j > 0:
            stack.append(k - nx)
        if j < ny - 1:
            stack.append(k + nx)
    field = [d - r for d in dist]
    for k in range(nx * ny):
        if field[k] > 0.0 and not seen[k]:
            field[k] = -h
    # Marching squares, the inside (field <= 0) on the left of every segment: walking a cell's corners
    # counter-clockwise (bottom left, bottom right, top right, top left), a segment runs from the edge where the walk
    # leaves the inside to the edge where it enters it; a saddle pairs each leaving edge with the next entering one when
    # the cell's middle is inside, else with the one before it.
    vertex, nxt = {}, {}
    inside = [f <= 0.0 for f in field]

    def crossing(key, ka, kb):
        if key not in vertex:
            fa, fb = field[ka], field[kb]
            t = fa / (fa - fb)
            ax, ay = x0 + (ka % nx) * h, y0 + (ka // nx) * h
            bx, by = x0 + (kb % nx) * h, y0 + (kb // nx) * h
            vertex[key] = (ax + (bx - ax) * t, ay + (by - ay) * t)
        return key

    for j in range(ny - 1):
        for i in range(nx - 1):
            bl, br = j * nx + i, j * nx + i + 1
            tl, tr = bl + nx, br + nx
            bits = (inside[bl], inside[br], inside[tr], inside[tl])
            if all(bits) or not any(bits):
                continue
            corners = (bl, br, tr, tl)
            edges = (('h', i, j), ('v', i + 1, j), ('h', i, j + 1), ('v', i, j))
            leave, enter = [], []
            for k in range(4):
                a, b = bits[k], bits[(k + 1) % 4]
                if a and not b:
                    leave.append(k)
                elif b and not a:
                    enter.append(k)
            if len(leave) == 1:
                pairs = [(leave[0], enter[0])]
            else:
                middle = (field[bl] + field[br] + field[tr] + field[tl]) <= 0.0
                pairs = []
                for k in leave:
                    after = [e for e in enter if e > k] + [e for e in enter if e < k]
                    pairs.append((k, after[0] if middle else after[-1]))
            for a, b in pairs:
                ka = crossing(edges[a], corners[a], corners[(a + 1) % 4])
                kb = crossing(edges[b], corners[b], corners[(b + 1) % 4])
                nxt[ka] = kb
    rings = []
    done = set()
    for start in list(nxt):
        if start in done:
            continue
        ring, key = [], start
        while key not in done:
            done.add(key)
            ring.append(vertex[key])
            key = nxt[key]
        ring.append(ring[0])
        ring = simplify_ring(ring, simplify_m)
        if len(ring) >= 4 and ring_area(ring) > 0.0:
            rings.append(ring)
    return rings


# --- the resort's ski area and its neighbours ------------------------------------------------------------------

AREA_ID_RE = re.compile(r'^(way|relation)/[1-9][0-9]*$')


def resort_areas(resort):
    """The ski-area ids, the neighbours and the derived buffer of a resorts.json entry, checked as packlib.py
    resort_entry checks them: `ski_area` is one id, a list of at least two distinct ids, or "derived" (the ids are then
    [] and the buffer in metres is `ski_area_buffer_m`, DERIVED_BUFFER_M by default; otherwise None); `neighbours`
    (optional) lists {id, name, reason} with distinct ids, none of them the resort's own."""
    slug, sa = resort.get('slug'), resort.get('ski_area')
    buffer_m = None
    if sa == 'derived':
        ids = []
        buffer_m = resort.get('ski_area_buffer_m', DERIVED_BUFFER_M)
        lo, hi = DERIVED_BUFFER_RANGE_M
        if isinstance(buffer_m, bool) or not isinstance(buffer_m, (int, float)) or not lo <= buffer_m <= hi:
            raise InputError(f'{slug}: ski_area_buffer_m must be a number of metres from {lo:g} to {hi:g}')
        buffer_m = float(buffer_m)
    elif 'ski_area_buffer_m' in resort:
        raise InputError(f'{slug}: ski_area_buffer_m goes only with "ski_area": "derived"')
    elif isinstance(sa, str) and AREA_ID_RE.match(sa):
        ids = [sa]
    elif (isinstance(sa, list) and len(sa) >= 2 and all(isinstance(x, str) and AREA_ID_RE.match(x) for x in sa)
            and len(set(sa)) == len(sa)):
        ids = list(sa)
    else:
        raise InputError(f'{slug}: ski_area must look like way/123 or relation/123, be a list of at least two distinct such ids, or be "derived"')
    nb = resort.get('neighbours')
    if nb is None:
        return ids, [], buffer_m
    if not isinstance(nb, list) or not nb:
        raise InputError(f'{slug}: neighbours must be a list of {{"id", "name", "reason"}} objects (leave it out for none)')
    seen = set()
    for i, n in enumerate(nb):
        where = f'{slug}: neighbours[{i}]'
        if not isinstance(n, dict) or set(n) != {'id', 'name', 'reason'}:
            raise InputError(f'{where} must hold exactly id, name and reason')
        if not isinstance(n['id'], str) or not AREA_ID_RE.match(n['id']):
            raise InputError(f'{where}: id must look like way/123 or relation/123')
        if not isinstance(n['name'], str) or not n['name'].strip():
            raise InputError(f'{where} ({n["id"]}): name must be the OSM name tag of that ski area')
        if not isinstance(n['reason'], str) or not n['reason'].strip():
            raise InputError(f'{where} ({n["id"]}): every neighbour needs a reason')
        if n['id'] in seen or n['id'] in ids:
            raise InputError(f'{where}: {n["id"]} appears twice, or is the resort\'s own ski area')
        seen.add(n['id'])
    return ids, nb, buffer_m


def area_rings(oid, ways, rels, nodes, what):
    """The node-id rings of a landuse=winter_sports area in the answer: (outer rings, inner rings, its element).
    `what` names it in the errors (a missing id, another kind of element, rings that do not close)."""
    kind, num = oid.split('/')
    el = (ways if kind == 'way' else rels).get(int(num))
    if el is None:
        raise InputError(f'{what} {oid} is not in the Overpass answer')
    if el['tags'].get('landuse') != 'winter_sports':
        raise InputError(f'{what} {oid} is not a landuse=winter_sports area (its landuse is {el["tags"].get("landuse")!r})')
    if kind == 'way':
        if len(el['nds']) < 4 or el['nds'][0] != el['nds'][-1]:
            raise InputError(f'{what} {oid} is not a closed way')
        outer_ids, inner_ids = [el['nds']], []
    else:
        members = [(ways[ref]['nds'], role) for t, ref, role in el['members'] if t == 'way' and ref in ways]
        try:
            outer_ids = assemble_rings([nds for nds, role in members if role in ('outer', '')])
            inner_ids = assemble_rings([nds for nds, role in members if role == 'inner'])
        except InputError as err:
            raise InputError(f'{what} {oid}: {err}') from None
        if not outer_ids:
            raise InputError(f'{what} {oid} has no outer ring in the Overpass answer')
    missing = [nid for ring in outer_ids + inner_ids for nid in ring if nid not in nodes]
    if missing:
        raise InputError(f'{what} {oid} lacks {len(missing)} node(s) in the Overpass answer')
    return outer_ids, inner_ids, el


def share_inside(lines, poly, closed=False):
    """Share of the lines' total length inside the polygon (one line: its length; a run area: its outer rings, the
    outline the out-of-bounds rule reads), and that length. closed: a stretch on the boundary counts as inside."""
    fracs = [inside_fraction(xy, poly, closed) for xy in lines]
    total = sum(L for _, L in fracs)
    if len(fracs) == 1:
        return fracs[0]
    return (sum(f * L for f, L in fracs) / total if total else 0.0), total


def owner_of(lines, polys, near_m=None):
    """Which of `polys` a feature belongs to (resorts.json neighbours, owner decision 2026-10-21). Its share in each is
    the part of its length (a run area: of its outline) inside or on the boundary of that polygon, so a line along an
    edge two polygons share lies in both, whichever side each is on. The first polygon (the resort's own) owns it when
    it holds at least OWNER_MIN_SHARE of it, even where another polygon overlaps it and holds more; else the one
    holding the most of it, at least OWNER_MIN_SHARE (ties: the lower index); else the nearest one within near_m
    metres (0 when they touch; no limit when near_m is math.inf), ties going to the larger share, then to the lower
    index. Returns (that index, or None when none is that near; the distance in metres when the distance decided,
    else None)."""
    near_m = NEIGHBOUR_NEAR_M if near_m is None else near_m
    shares = [share_inside(lines, poly, closed=True)[0] for poly in polys]
    held = [i for i, s in enumerate(shares) if s >= OWNER_MIN_SHARE]
    if held:
        return (0 if 0 in held else min(held, key=lambda i: (-shares[i], i))), None
    dist = [0.0 if s > 0.0 or (lines and lines[0] and poly.covers(*lines[0][0])) else poly.distance_to(lines, near_m)
            for s, poly in zip(shares, polys)]
    near = [i for i, d in enumerate(dist) if d <= near_m]
    if not near:
        return None, None
    who = min(near, key=lambda i: (dist[i], -shares[i], i))
    return who, dist[who]


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

    # 3. The ski-area polygon: one OSM id, or one per mountain (their union), and the neighbours' polygons. Or derived
    # from the kept lifts and runs (ski_area "derived"): then there is no polygon yet, and everything that reads one
    # (the in-bounds share of each run, the overlap note of a neighbour) waits for step 5a.
    ski_ids, neighbours, derived_buffer_m = resort_areas(resort)
    derived = derived_buffer_m is not None
    parts = []   # per listed id: (id, its element, its rings in lon/lat (outer first), its Polygon, its area in km2)
    part_rings = []   # all their rings as node ids, closed
    sa_poly = None
    for oid in ski_ids:
        outer_ids, inner_ids, sa = area_rings(oid, ways, rels, nodes, 'ski area')
        rings_ll = [[nodes[nid] for nid in ring] for ring in outer_ids + inner_ids]
        area_km2 = (sum(ring_area([proj(*p) for p in [nodes[i] for i in r]]) for r in outer_ids)
                    - sum(ring_area([proj(*p) for p in [nodes[i] for i in r]]) for r in inner_ids)) / 1e6
        parts.append((oid, sa, rings_ll, Polygon([[proj(*p) for p in ring] for ring in rings_ll]), area_km2))
        part_rings += outer_ids + inner_ids
    for i, (a_id, _, _, a_poly, _) in enumerate(parts):
        for b_id, _, _, b_poly, _ in parts[i + 1:]:
            if polygons_overlap(a_poly, b_poly):
                raise InputError(f'the ski areas {a_id} and {b_id} overlap: a resort lists polygons that share no area '
                                 '(where they did, the even-odd test of their union would punch a hole)')
    sa_rings_ll = [ring for part in parts for ring in part[2]]
    if derived:
        if SKI_AREA_RELATION_ID in rels:
            raise InputError(f'the Overpass answer already holds relation {SKI_AREA_RELATION_ID}, the id the ski area is written under')
        sa_area_km2 = 0.0
        report['ski_area'] = {'source': 'derived', 'buffer_m': derived_buffer_m, 'name': glyph_safe(resort.get('name'), ranges)}
    elif len(parts) == 1:
        sa_kind, sa_num = ski_ids[0].split('/')
        sa_num = int(sa_num)
        sa_poly = parts[0][3]
        sa_area_km2 = sum(part[4] for part in parts)
        report['ski_area'] = {'id': ski_ids[0], 'name': glyph_safe(parts[0][1]['tags'].get('name'), ranges), 'area_km2': round(sa_area_km2, 2)}
    else:
        sa_poly = Polygon([[proj(*p) for p in ring] for ring in sa_rings_ll])
        sa_area_km2 = sum(part[4] for part in parts)
        if SKI_AREA_RELATION_ID in rels:
            raise InputError(f'the Overpass answer already holds relation {SKI_AREA_RELATION_ID}, the id the ski areas are written under')
        # The union's outline, the rings the ski_area relation is written with (step 7): one closed way each.
        sa_outline, shared = union_rings(part_rings)
        if not sa_outline:
            raise InputError(f'the listed ski areas {", ".join(ski_ids)} leave no outline')
        taken = [wid for wid in range(SKI_AREA_RELATION_ID, SKI_AREA_RELATION_ID + len(sa_outline)) if wid in ways]
        if taken:
            raise InputError(f'the Overpass answer already holds way {taken[0]}, an id the ski areas\' rings are written under')
        sa_roles = ring_roles([[proj(*nodes[nid]) for nid in ring] for ring in sa_outline])
        # Several mountains: one feature named after the resort (each polygon keeps its own OSM name in the report).
        report['ski_area'] = {'ids': ski_ids, 'name': glyph_safe(resort.get('name'), ranges), 'area_km2': round(sa_area_km2, 2),
                              'written_as': f'relation/{SKI_AREA_RELATION_ID}',
                              'rings': {'outer': sa_roles.count('outer'), 'inner': sa_roles.count('inner')},
                              # The border two listed polygons share (the same nodes), left out of the outline.
                              'shared_border_m': round(sum(line_length([proj(*nodes[u]), proj(*nodes[v])]) for u, v in shared)),
                              'parts': [{'id': oid, 'name': glyph_safe(el['tags'].get('name'), ranges), 'area_km2': round(km2, 2)}
                                        for oid, el, _, _, km2 in parts]}
    listed = set(ski_ids)

    # Neighbours: each one in the answer as a landuse=winter_sports area whose OSM name is the one resorts.json gives
    # (checked like an override's expect, so a renamed or redrawn neighbour stops the build).
    nb_polys = []
    for n in neighbours:
        outer_ids, inner_ids, el = area_rings(n['id'], ways, rels, nodes, 'neighbour')
        if el['tags'].get('name') != n['name']:
            raise InputError(f'neighbour {n["id"]}: its OSM name is {el["tags"].get("name")!r}, not {n["name"]!r} '
                             '(renamed or redrawn in OSM? check it, then update resorts.json)')
        nb_polys.append(Polygon([[proj(*nodes[nid]) for nid in ring] for ring in outer_ids + inner_ids]))
    if neighbours:
        # Per neighbour: whether its polygon overlaps the ski area (what the ski area holds at least half of stays
        # then, though the neighbour holds more; with a derived ski area, known only once it is derived, step 5a); the
        # ids left out; by_distance: those lying less than half in any polygon, given to the neighbour by the 250 m
        # rule (never with a derived ski area: there is no resort polygon to measure the distance against, so a
        # feature is a neighbour's only when that neighbour holds at least half of it).
        report['neighbours'] = [{'id': n['id'], 'name': n['name'], 'overlaps_ski_area': None if derived else polygons_overlap(sa_poly, poly),
                                 'lifts': [], 'runs': [], 'run_areas': [], 'stations': [], 'by_distance': []}
                                for n, poly in zip(neighbours, nb_polys)]
        for nb in report['neighbours']:
            if nb['overlaps_ski_area']:
                print(f'normalize_osm: note: the neighbour {nb["id"]} overlaps the ski area; a feature the ski area holds '
                      'at least half of stays on the map', file=sys.stderr)
    owners = [sa_poly] + nb_polys

    def neighbour_owner(lines):
        """(the index in report['neighbours'] of the listed neighbour this feature belongs to, or None: the resort's,
        or nobody's, kept; whether the 250 m rule decided it)."""
        if not nb_polys:
            return None, False
        if derived:
            shares = [share_inside(lines, poly, closed=True)[0] for poly in nb_polys]
            held = [i for i, s in enumerate(shares) if s >= OWNER_MIN_SHARE]
            return (min(held, key=lambda i: (-shares[i], i)), False) if held else (None, False)
        who, dist = owner_of(lines, owners)
        return (None, False) if who in (None, 0) else (who - 1, dist is not None)

    def left_out(n, group, oid, by_distance=False):
        report['neighbours'][n][group].append(oid)
        if by_distance:
            report['neighbours'][n]['by_distance'].append(oid)
        drop('neighbour')

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
    run_xy = []      # and their projected lines
    pending = []     # runs waiting for the ski-area polygon (derived: all of them, settled in step 5a)

    def settle_run(sb, extra, key, ptype, difficulty, flags, name, ref, lines, area, size, info, backcountry, changes):
        """The in-bounds decision of one run against the ski-area polygon, and its tags and report entry, in one
        order whichever path calls it: at once with a listed polygon, after step 5a with a derived one."""
        if area:
            fracs = [inside_fraction(r, sa_poly) for r in lines]
            total = sum(L for _, L in fracs)
            in_frac = sum(f * L for f, L in fracs) / total if total else 0.0
        else:
            in_frac, _ = inside_fraction(lines[0], sa_poly)
        oob = backcountry and in_frac < OOB_MAX_INSIDE_FRACTION
        if 'out_of_bounds' in changes:
            oob = changes['out_of_bounds']
        sb.update({'sb:layer': 'piste_area' if area else 'piste', 'sb:type': ptype, 'sb:difficulty': difficulty})
        for flag, on in (*flags, ('sb:out_of_bounds', oob)):
            if on:
                sb[flag] = 'yes'
        if name:
            sb['sb:name'] = name
        if ref:
            sb['sb:ref'] = ref
        info = {**info, 'in_frac': round(in_frac, 3), **size}
        if oob:
            report['out_of_bounds'].append(info)
        elif in_frac < OOB_MAX_INSIDE_FRACTION:
            report['outside_ski_area_in_bounds'].append(info)
        extra.update({'out_of_bounds': oob, 'in_frac': round(in_frac, 3), **size})

    candidates = [('way', wid, ways[wid]['tags']) for wid in sorted(ways)]
    candidates += [('relation', rid, rels[rid]['tags']) for rid in sorted(rels) if rels[rid]['tags'].get('type') == 'multipolygon']
    for otype, oid, t in candidates:
        if t.get('aerialway') in lift_kinds or f'{otype}/{oid}' in listed:
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
            size = {'area_m2': round(sum(ring_area(r) for r in outline[:n_outer]) - sum(ring_area(r) for r in outline[n_outer:]))}
            lines = outline[:n_outer]
        else:
            xy = [proj(*p) for p in coords]
            size = {'length_m': round(line_length(xy))}
            lines = [xy]
        # A listed neighbour's run or run area is left out (before the ranks, so it takes no share of them).
        n, near = neighbour_owner(lines)
        if n is not None:
            left_out(n, 'run_areas' if area else 'runs', key, near)
            continue
        backcountry = 'backcountry' in grooming or t.get('patrolled') == 'no'
        info = {'id': key, 'name': name, 'difficulty': difficulty, 'grooming': ';'.join(sorted(grooming)) or None,
                'patrolled': t.get('patrolled')}
        geom = ({'type': 'Polygon', 'coordinates': rings_ll} if area else {'type': 'LineString', 'coordinates': coords})
        sb, extra = {}, {}
        settle = (sb, extra, key, ptype, difficulty, (('sb:ungroomed', ungroomed), ('sb:gladed', gladed), ('sb:park', park)),
                  name, ref, lines, area, size, info, backcountry, changes)
        if derived:
            pending.append(settle)
        else:
            settle_run(*settle)
        kept.append((otype, oid, sb, geom, extra))
        if not area:
            run_lines.append(len(kept) - 1)
            run_xy.append(xy)

    # 5. Lifts.
    lift_segments = []
    lift_xy = []   # the kept lifts' projected lines (the derived ski area, step 5a)
    lift_ends = set()   # node ids of the kept lifts' ends
    neighbour_lifts = []   # (segment, neighbour index) of the lifts left out as a listed neighbour's
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
        n, near = neighbour_owner([[proj(*p) for p in coords]])
        if n is not None:
            # A listed neighbour's lift is left out, and its stations go with it (step 6).
            left_out(n, 'lifts', key, near)
            xy = [proj(*p) for p in coords]
            neighbour_lifts += [(seg, n) for seg in zip(xy, xy[1:])]
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
        lift_xy.append(xy)
        lift_ends.update((ways[wid]['nds'][0], ways[wid]['nds'][-1]))
        kept.append(('way', wid, sb, {'type': 'LineString', 'coordinates': coords}, {'length_m': round(line_length(xy))}))

    # 5a. The derived ski area (ski_area "derived"): the kept lifts and runs, as they stand after the overrides and the
    # neighbour rule, buffered and unioned (derive_ski_area), as one relation of closed rings with nodes of its own.
    # Then the runs' in-bounds decisions, which waited for it: by construction every kept run lies inside, so none is
    # out of bounds unless an override says so.
    sa_rings_xy = []
    if derived:
        run_outlines = [settle[8] for settle in pending]   # each run's projected line, or a run area's outer rings
        source_lines = lift_xy + [xy for lines in run_outlines for xy in lines]
        if not source_lines:
            raise InputError(f'{a.slug}: ski_area is "derived" but no lift or run is left to derive it from '
                             '(check the overrides and the neighbours, or map the resort\'s lifts and runs in OpenStreetMap)')
        rings_xy = derive_ski_area(source_lines, derived_buffer_m)
        if not rings_xy:
            raise InputError(f'{a.slug}: the derived ski area has no outline')
        # The rings' nodes, written at 7 decimals like every node: the polygon of every inside test is the one written,
        # so the GeoJSON, the OSM file and the tests agree to the last digit. Their ids follow the answer's highest
        # node id (free by construction; see SKI_AREA_RELATION_ID's note on Planetiler's node index).
        next_nid = max(nodes) + 1 if nodes else 1
        sa_outline, sa_roles = [], []
        for ring in rings_xy:
            ring_ids = []
            for x, y in ring[:-1]:
                nodes[next_nid] = (round(x / proj.kx + proj.lon0, 7), round(y / proj.k + proj.lat0, 7))
                ring_ids.append(next_nid)
                next_nid += 1
            ring_ids.append(ring_ids[0])
            sa_outline.append(ring_ids)
            sa_roles.append('outer')
        sa_rings_ll = [[nodes[nid] for nid in ring] for ring in sa_outline]
        sa_rings_xy = [[proj(*p) for p in ring] for ring in sa_rings_ll]
        sa_poly = Polygon(sa_rings_xy)
        parts = [(f'part/{i + 1}', None, [ring_ll], Polygon([ring_xy]), ring_area(ring_xy) / 1e6)
                 for i, (ring_ll, ring_xy) in enumerate(zip(sa_rings_ll, sa_rings_xy))]
        sa_area_km2 = sum(part[4] for part in parts)
        for settle in pending:
            settle_run(*settle)
        # Every source line lies inside (the buffer is never under the simplification's tolerance): checked, not assumed.
        # inside_fraction adds the samples' shares in floating point, so a line wholly inside reads 1 - 1e-16 at times.
        def held(xy):
            return inside_fraction(xy, sa_poly, closed=True)[0] >= 1.0 - 1e-9
        outside = [k[0] + '/' + str(k[1]) for k in kept if k[2].get('sb:layer') in ('piste', 'lift')
                   and not held([proj(*p) for p in k[3]['coordinates']])]
        outside += [k[0] + '/' + str(k[1]) for k in kept if k[2].get('sb:layer') == 'piste_area'
                    and not all(held([proj(*p) for p in ring]) for ring in k[3]['coordinates'])]
        if outside:
            raise InputError(f'the derived ski area does not hold {", ".join(outside[:5])}: a bug in derive_ski_area')
        report['ski_area'].update({
            'lifts': len(lift_xy), 'runs': len(pending), 'parts': len(parts), 'area_km2': round(sa_area_km2, 2),
            'grid_m': DERIVED_GRID_M, 'simplify_m': DERIVED_SIMPLIFY_M, 'written_as': f'relation/{SKI_AREA_RELATION_ID}',
            'rings': {'outer': len(parts), 'inner': 0},
            'parts_km2': [round(part[4], 3) for part in parts]})
        for nb, poly in zip(report.get('neighbours', []), nb_polys):
            nb['overlaps_ski_area'] = polygons_overlap(sa_poly, poly)
            if nb['overlaps_ski_area']:
                print(f'normalize_osm: note: the neighbour {nb["id"]} overlaps the derived ski area', file=sys.stderr)

    # Ranks: the trunk runs, minor runs and the others (the style draws the overview zooms by rank). A named run is all
    # the ways of that name; with several mountains, all the ways of that name on one mountain (the listed polygon
    # that owns the way by the neighbour rule, else the nearest one), so same-named runs on two mountains rank apart.
    # (A derived ski area's parts are not mountains: a named run is all the ways of that name.)
    if len(ski_ids) > 1:
        mountains = [p[3] for p in parts]
        keys = [(kept[i][2]['sb:name'], owner_of([xy], mountains, near_m=math.inf)[0]) if kept[i][2].get('sb:name') else None
                for i, xy in zip(run_lines, run_xy)]
    else:
        keys = [kept[i][2].get('sb:name') for i in run_lines]
    ranks, by_rating = run_ranks([(key, kept[i][4]['length_m'], kept[i][4]['out_of_bounds'],
                                   rating_of(kept[i][2]['sb:difficulty'], kept[i][2].get('sb:park') == 'yes'))
                                  for key, i in zip(keys, run_lines)])
    for i, rank in zip(run_lines, ranks):
        kept[i][2]['sb:rank'] = str(rank)
    report['ranks'] = {'trunk_share': TRUNK_SHARE, 'trunk_per': 'rating', 'minor_run_m': MINOR_RUN_M,
                       'ratings': by_rating, 'runs': {str(r): ranks.count(r) for r in (1, 2, 3)}}
    if len(ski_ids) > 1:
        report['ranks']['named_run'] = 'the ways of one name on one mountain'

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

    def neighbour_station(lonlat):
        """The neighbour whose left-out lift is the station's nearest lift within STATION_MAX_DISTANCE_M (a kept lift
        as near wins), or None."""
        if not neighbour_lifts:
            return None
        p = proj(*lonlat)
        theirs = min(((point_segment_distance(p, a2, b2), n) for (a2, b2), n in neighbour_lifts), key=lambda x: x[0])
        if theirs[0] > STATION_MAX_DISTANCE_M:
            return None
        ours = min((point_segment_distance(p, a2, b2) for a2, b2 in lift_segments), default=math.inf)
        return None if ours <= theirs[0] else theirs[1]

    for otype, oid, t, centre in stations:
        key = f'{otype}/{oid}'
        o = applied.get(key)
        if o and o.get('hide'):
            drop('hidden_by_override')
            continue
        n = neighbour_station(centre)
        if n is not None:
            left_out(n, 'stations', key)
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

    # 7. The ski area itself: one feature, the OSM polygon of one id, or for several a multipolygon relation
    # (SKI_AREA_RELATION_ID) of the union's rings, each one closed untagged way of its own (ids from
    # SKI_AREA_RELATION_ID up). The GeoJSON keeps one member per listed polygon, for coverage.py's radius per mountain.
    # A derived ski area is written the same way, one part per ring, whatever their number.
    sb = {'sb:layer': 'ski_area'}
    if report['ski_area']['name']:
        sb['sb:name'] = report['ski_area']['name']
    extra_rels = {}
    if len(parts) == 1 and not derived:
        kept.append((sa_kind, sa_num, sb, {'type': 'Polygon', 'coordinates': sa_rings_ll}, {'area_m2': round(sa_area_km2 * 1e6)}))
    else:
        members = []
        for i, (ring, role) in enumerate(zip(sa_outline, sa_roles)):
            ways[SKI_AREA_RELATION_ID + i] = {'nds': ring, 'tags': {}}
            members.append(('way', SKI_AREA_RELATION_ID + i, role))
        extra_rels[SKI_AREA_RELATION_ID] = members
        kept.append(('relation', SKI_AREA_RELATION_ID, sb, {'type': 'MultiPolygon', 'coordinates': [part[2] for part in parts]},
                     {'osm': 'derived' if derived else ','.join(ski_ids), 'area_m2': round(sa_area_km2 * 1e6)}))

    for _, _, sbt, _, _ in kept:
        report['kept'][sbt['sb:layer']] = report['kept'].get(sbt['sb:layer'], 0) + 1
    report['dropped'] = dict(sorted(report['dropped'].items()))
    report['out_of_bounds'].sort(key=lambda r: r['id'])
    report['outside_ski_area_in_bounds'].sort(key=lambda r: r['id'])
    for nb in report.get('neighbours', []):
        for group in ('lifts', 'runs', 'run_areas', 'stations', 'by_distance'):
            nb[group].sort(key=lambda oid: (oid.split('/')[0], int(oid.split('/')[1])))

    write_osm(a.out_osm, kept, nodes, ways, rels, bounds, extra_rels)
    write_json(a.out_features, features(kept))
    write_json(a.out_report, report)
    k = report['kept']
    print(f'{a.slug}: osm_base {osm_base}; kept {k.get("piste", 0)} runs, {k.get("piste_area", 0)} run areas, '
          f'{k.get("lift", 0)} lifts, {k.get("lift_station", 0)} stations; {len(report["out_of_bounds"])} out of bounds; '
          f'{len(report["overrides"]["applied"])} overrides applied; dropped {sum(report["dropped"].values())}'
          + (f' ({report["dropped"].get("neighbour", 0)} as {len(neighbours)} listed neighbours\')' if neighbours else ''))
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


def write_osm(path, kept, nodes, ways, rels, bounds, extra_rels=None):
    """Writes only the kept elements, with their sb:* tags, plus the untagged member ways and nodes they need.
    `extra_rels` gives the members of relations that are not in the answer (the ski area of several mountains)."""
    extra_rels = extra_rels or {}

    def members_of(rid):
        return extra_rels[rid] if rid in extra_rels else rels[rid]['members']

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
        for mt, ref, _ in members_of(rid):
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
                      for mt, ref, role in members_of(rid) if mt == 'way' and ref in ways)
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

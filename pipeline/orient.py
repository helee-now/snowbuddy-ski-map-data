#!/usr/bin/env python3
"""Turns runs downhill and lifts uphill from the elevation model, so the style can draw arrows only where the
direction is right (ADR-036, amendment 2026-10-17). Runs in the GDAL image (GDAL's Python bindings and numpy, for
reading the model); everything else is plain Python, so the tests run it without GDAL.

  orient.py <in.osm> <dem.tif> <out.osm> <report.json>

The input is normalize_osm.py's XML (only sb:* tags); the output is the same data with:
  - runs (sb:layer=piste lines) joined into chains: ways with the same sb:* tags that meet end to end at a node where
    no third way of those tags ends become one way, so a run split into short ways is decided, and drawn, as a whole.
    Planetiler then draws each chain as one line: the profile does not merge runs itself any more, because its merge
    can join two runs that flow into one junction head to head, and an arrow on one of them would point uphill. Ways
    that a relation uses (run areas) and closed ways stay alone;
  - each chain read every STEP_M along its line (bilinear) and the profile smoothed over SMOOTH_M on each side. A
    chain whose smoothed ends are at least max(RUN_MIN_DROP_M, RUN_MIN_GRADE x length) apart, and whose climbs on the
    way down (rises of more than CLIMB_BAND_M) add up to at most MAX_COUNTER_SHARE of that drop, is written to run
    downhill (reversed when OpenStreetMap draws it uphill) and tagged sb:oriented=yes. Chains too flat, with climbs
    that make the direction ambiguous, closed into a loop or without elevation keep OpenStreetMap's direction and get
    no tag, so the style draws them without arrows;
  - each lift (sb:layer=lift), one way at a time, decided the same way to run uphill (LIFT_MIN_GRADE).
Everything else is copied as it is. The report gives the counts, the ways reversed and the chains and lifts left
without a direction, with the reason.

Exit codes: 0 done, 2 bad input.
"""
import json
import math
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

STEP_M = 10.0
SMOOTH_M = 20.0
RUN_MIN_DROP_M = 10.0
RUN_MIN_GRADE = 0.03
LIFT_MIN_DROP_M = 10.0
LIFT_MIN_GRADE = 0.05
MAX_COUNTER_SHARE = 0.3
CLIMB_BAND_M = 3.0
M_PER_DEG = 6371008.8 * math.pi / 180.0
ORIENTED = 'sb:oriented'

PARAMS = {'step_m': STEP_M, 'smooth_m': SMOOTH_M, 'run_min_drop_m': RUN_MIN_DROP_M, 'run_min_grade': RUN_MIN_GRADE,
          'lift_min_drop_m': LIFT_MIN_DROP_M, 'lift_min_grade': LIFT_MIN_GRADE, 'max_counter_share': MAX_COUNTER_SHARE,
          'climb_band_m': CLIMB_BAND_M}


class InputError(Exception):
    pass


# --- the OSM XML (normalize_osm.py's format) --------------------------------------------------------------------

def read_osm(path):
    """Returns {'bounds': attrs or None, 'nodes': {id: (lat, lon, tags)}, 'ways': {id: (nds, tags)},
    'rels': {id: (members, tags)}}, with coordinates kept as the strings written."""
    doc = {'bounds': None, 'nodes': {}, 'ways': {}, 'rels': {}}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as err:
        raise InputError(f'{path}: {err}') from None
    for el in root:
        tags = {t.get('k'): t.get('v') for t in el.findall('tag')}
        if el.tag == 'bounds':
            doc['bounds'] = dict(el.attrib)
        elif el.tag == 'node':
            doc['nodes'][int(el.get('id'))] = (el.get('lat'), el.get('lon'), tags)
        elif el.tag == 'way':
            doc['ways'][int(el.get('id'))] = ([int(n.get('ref')) for n in el.findall('nd')], tags)
        elif el.tag == 'relation':
            doc['rels'][int(el.get('id'))] = ([(m.get('type'), int(m.get('ref')), m.get('role') or '') for m in el.findall('member')], tags)
    return doc


def write_osm(path, doc):
    def tags_xml(tags):
        return ''.join(f'    <tag k={quoteattr(k)} v={quoteattr(v)}/>\n' for k, v in sorted(tags.items()))

    parts = ["<?xml version='1.0' encoding='UTF-8'?>\n", '<osm version="0.6" generator="snowbuddy normalize_osm.py, orient.py">\n']
    b = doc['bounds']
    if b:
        parts.append(f'  <bounds minlat="{b["minlat"]}" minlon="{b["minlon"]}" maxlat="{b["maxlat"]}" maxlon="{b["maxlon"]}"/>\n')
    for nid in sorted(doc['nodes']):
        lat, lon, tags = doc['nodes'][nid]
        if tags:
            parts.append(f'  <node id="{nid}" lat="{lat}" lon="{lon}">\n{tags_xml(tags)}  </node>\n')
        else:
            parts.append(f'  <node id="{nid}" lat="{lat}" lon="{lon}"/>\n')
    for wid in sorted(doc['ways']):
        nds, tags = doc['ways'][wid]
        parts.append(f'  <way id="{wid}">\n' + ''.join(f'    <nd ref="{n}"/>\n' for n in nds) + f'{tags_xml(tags)}  </way>\n')
    for rid in sorted(doc['rels']):
        members, tags = doc['rels'][rid]
        mem = ''.join(f'    <member type="{t}" ref="{r}" role={quoteattr(role)}/>\n' for t, r, role in members)
        parts.append(f'  <relation id="{rid}">\n{mem}{tags_xml(tags)}  </relation>\n')
    parts.append('</osm>\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))


# --- chains ------------------------------------------------------------------------------------------------------

def chains(lines, alone=()):
    """Joins lines with the same tags end to end. `lines` maps an id to (node ids, tags, directed): a directed line
    runs from its first node to its last. Two lines join at a node where exactly two line ends of their tag group
    meet: two directed lines only head to tail, two undirected lines either way round, a directed and an undirected
    line never. Lines in `alone` and closed lines are never joined. Returns the chains, each a list of
    (line id, reversed) in order along it, ordered by tag group and then by id."""
    groups = {}
    for wid, (nds, tags, _) in lines.items():
        groups.setdefault(tuple(sorted(tags.items())), []).append(wid)
    out = []
    for key in sorted(groups):
        ids = sorted(groups[key])
        single = {wid for wid in ids if wid in alone or lines[wid][0][0] == lines[wid][0][-1]}
        ends = {}
        for wid in ids:
            if wid not in single:
                nds = lines[wid][0]
                ends.setdefault(nds[0], []).append(wid)
                ends.setdefault(nds[-1], []).append(wid)
        used = set()

        def other(node, wid):
            """The line that `wid` can join at `node`, entering it there, as (id, reversed); or None."""
            pair = ends.get(node, ())
            if len(pair) != 2:
                return None
            nxt = pair[1] if pair[0] == wid else pair[0]
            nn, _, directed = lines[nxt]
            if directed != lines[wid][2]:
                return None
            if directed:
                return (nxt, False) if nn[0] == node else None
            return nxt, nn[-1] == node

        def walk(start, rev):
            chain = [(start, rev)]
            used.add(start)
            nds = lines[start][0]
            tail = nds[0] if rev else nds[-1]
            while True:
                step = other(tail, chain[-1][0])
                if step is None or step[0] in used:
                    return chain
                chain.append(step)
                used.add(step[0])
                nn = lines[step[0]][0]
                tail = nn[0] if step[1] else nn[-1]

        def joins_at(wid, node):
            """Whether a line can continue `wid` through `node`, one of its ends: a directed line is entered only
            through its first node, from a line ending there, and left only through its last, into a line starting
            there."""
            pair = ends.get(node, ())
            if len(pair) != 2:
                return False
            nb = pair[1] if pair[0] == wid else pair[0]
            nn, _, directed = lines[nb]
            if directed != lines[wid][2]:
                return False
            if not directed:
                return True
            return nn[-1] == node if node == lines[wid][0][0] else nn[0] == node

        for wid in ids:
            if wid in used:
                continue
            nds, _, directed = lines[wid]
            if wid in single:
                used.add(wid)
                out.append([(wid, False)])
            elif not joins_at(wid, nds[0]):
                out.append(walk(wid, False))
            elif not directed and not joins_at(wid, nds[-1]):
                out.append(walk(wid, True))
        for wid in ids:  # what is left closes into loops
            if wid not in used:
                out.append(walk(wid, False))
    return out


def chain_nodes(chain, lines):
    """The node ids along a chain, each joint once."""
    seq = []
    for wid, rev in chain:
        nds = lines[wid][0][::-1] if rev else lines[wid][0]
        if seq and seq[-1] != nds[0]:
            raise InputError(f'way {wid} does not continue its chain')
        seq.extend(nds if not seq else nds[1:])
    return seq


# --- profiles and the decision ------------------------------------------------------------------------------------

def densify(coords, step=STEP_M):
    """Points along a lon/lat line no more than `step` metres apart (each segment cut evenly), and its length."""
    out = [coords[0]]
    length = 0.0
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        d = math.hypot((x2 - x1) * math.cos(math.radians((y1 + y2) / 2.0)), y2 - y1) * M_PER_DEG
        n = max(1, int(math.ceil(d / step)))
        out.extend((x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(1, n + 1))
        length += d
    return out, length


def smooth(z, k):
    """Moving average over k samples on each side (fewer at the ends)."""
    n = len(z)
    return [sum(z[max(0, i - k):min(n, i + k + 1)]) / (min(n, i + k + 1) - max(0, i - k)) for i in range(n)]


def climb(z, band):
    """The total climb along z, counting only rises of more than `band` from the lowest point since the last one."""
    total, low = 0.0, z[0]
    for v in z[1:]:
        if v < low:
            low = v
        elif v - low > band:
            total += v - low
            low = v
    return total


def decide(z, length_m, want, min_drop_m, min_grade, max_counter_share=MAX_COUNTER_SHARE, band_m=CLIMB_BAND_M,
           smooth_k=int(round(SMOOTH_M / STEP_M))):
    """Whether a line drawn with the elevation profile `z` (about STEP_M apart; None where the model has no data)
    runs `want` ('down' for runs, 'up' for lifts) clearly enough for an arrow, and whether to reverse it for that.
    Returns {'reverse', 'oriented', 'reason' (clear, flat, ambiguous, no_elevation), 'drop_m', 'counter_m'}."""
    if len(z) < 2 or any(v is None for v in z):
        return {'reverse': False, 'oriented': False, 'reason': 'no_elevation', 'drop_m': None, 'counter_m': None}
    sign = 1.0 if want == 'down' else -1.0
    s = smooth([sign * v for v in z], smooth_k)
    drop = s[0] - s[-1]
    if abs(drop) < max(min_drop_m, min_grade * length_m):
        return {'reverse': False, 'oriented': False, 'reason': 'flat', 'drop_m': round(abs(drop), 1), 'counter_m': None}
    reverse = drop < 0
    counter = climb(s[::-1] if reverse else s, band_m)
    if counter > max_counter_share * abs(drop):
        return {'reverse': False, 'oriented': False, 'reason': 'ambiguous', 'drop_m': round(abs(drop), 1), 'counter_m': round(counter, 1)}
    return {'reverse': reverse, 'oriented': True, 'reason': 'clear', 'drop_m': round(abs(drop), 1), 'counter_m': round(counter, 1)}


# --- the work ------------------------------------------------------------------------------------------------------

def orient(doc, profile):
    """Orients the runs and lifts of `doc` in place. `profile(node ids)` returns (elevations along the line, length in
    metres). Returns the report."""
    ways, rels = doc['ways'], doc['rels']
    in_relation = {ref for members, _ in rels.values() for t, ref, _ in members if t == 'way'}
    report = {'params': PARAMS,
              'runs': {'ways': 0, 'lines': 0, 'joined_ways': 0, 'oriented': 0, 'ways_reversed': [], 'without_direction': []},
              'lifts': {'ways': 0, 'oriented': 0, 'ways_reversed': [], 'without_direction': []}}
    r = report['runs']

    def decide_line(nds, want):
        if nds[0] == nds[-1]:
            return {'reverse': False, 'oriented': False, 'reason': 'loop', 'drop_m': None, 'counter_m': None}, None
        z, length = profile(nds)
        if want == 'down':
            return decide(z, length, 'down', RUN_MIN_DROP_M, RUN_MIN_GRADE), length
        return decide(z, length, 'up', LIFT_MIN_DROP_M, LIFT_MIN_GRADE), length

    # Runs: each way on its own, then joined into chains (directed ways head to tail only); a chain of ways without a
    # direction of their own is decided again as a whole (a run split into short ways).
    lines, decided = {}, {}
    for wid in sorted(w for w, (_, t) in ways.items() if t.get('sb:layer') == 'piste'):
        nds, tags = ways[wid]
        d, length = decide_line(nds, 'down')
        decided[wid] = (d, length)
        lines[wid] = (nds[::-1] if d['reverse'] else nds, tags, d['oriented'])
    r['ways'] = len(lines)
    for chain in chains(lines, alone=in_relation):
        seq = chain_nodes(chain, lines)
        tags = dict(lines[chain[0][0]][1])
        oriented = lines[chain[0][0]][2]
        # Each member's direction against OpenStreetMap's: its own decision, then its place in the chain.
        flipped = {wid: decided[wid][0]['reverse'] != rev for wid, rev in chain}
        d, length = decided[chain[0][0]]
        if len(chain) > 1:
            r['joined_ways'] += len(chain)
            if not oriented:
                d, length = decide_line(seq, 'down')
                oriented = d['oriented']
                if d['reverse']:
                    seq = seq[::-1]
                    flipped = {wid: not f for wid, f in flipped.items()}
        r['lines'] += 1
        if oriented:
            tags[ORIENTED] = 'yes'
            r['oriented'] += 1
            r['ways_reversed'] += [wid for wid, f in flipped.items() if f]
        else:
            r['without_direction'].append({'ways': sorted(flipped), 'name': tags.get('sb:name'), 'reason': d['reason'],
                                           'length_m': round(length) if length is not None else None, 'drop_m': d['drop_m'],
                                           'counter_m': d['counter_m']})
        for wid, _ in chain:
            del ways[wid]
        ways[min(flipped)] = (seq, tags)

    # Lifts: one way at a time, uphill.
    for wid in sorted(w for w, (_, t) in ways.items() if t.get('sb:layer') == 'lift'):
        nds, tags = ways[wid]
        report['lifts']['ways'] += 1
        d, length = decide_line(nds, 'up')
        if d['oriented']:
            ways[wid] = (nds[::-1] if d['reverse'] else nds, {**tags, ORIENTED: 'yes'})
            report['lifts']['oriented'] += 1
            if d['reverse']:
                report['lifts']['ways_reversed'].append(wid)
        else:
            report['lifts']['without_direction'].append({'way': wid, 'name': tags.get('sb:name'), 'kind': tags.get('sb:kind'),
                                                         'reason': d['reason'], 'length_m': round(length) if length is not None else None,
                                                         'drop_m': d['drop_m'], 'counter_m': d['counter_m']})
    r['ways_reversed'].sort()
    r['without_direction'].sort(key=lambda x: x['ways'][0])
    return report


class Elevation:
    """Bilinear reads of a single-band elevation GeoTIFF (north up, any CRS GDAL knows) at lon/lat points."""

    def __init__(self, path):
        import numpy as np
        from osgeo import gdal, osr
        gdal.UseExceptions()
        ds = gdal.Open(path)
        band = ds.GetRasterBand(1)
        self.np = np
        self.a = band.ReadAsArray().astype(np.float64)
        nd = band.GetNoDataValue()
        self.ok = np.isfinite(self.a) & (self.a > -1000.0) & ((self.a != nd) if nd is not None else True)
        self.gt = ds.GetGeoTransform()
        if self.gt[2] != 0 or self.gt[4] != 0:
            raise InputError(f'{path} is not north up')
        wgs, srs = osr.SpatialReference(), osr.SpatialReference(wkt=ds.GetProjection())
        wgs.ImportFromEPSG(4326)
        for ref in (wgs, srs):
            ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        self.tr = osr.CoordinateTransformation(wgs, srs)

    def __call__(self, lonlats):
        np = self.np
        xy = np.array(self.tr.TransformPoints([(lon, lat) for lon, lat in lonlats]))[:, :2]
        c = (xy[:, 0] - self.gt[0]) / self.gt[1] - 0.5
        r = (xy[:, 1] - self.gt[3]) / self.gt[5] - 0.5
        c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
        h, w = self.a.shape
        inside = (c0 >= 0) & (r0 >= 0) & (c0 + 1 < w) & (r0 + 1 < h)
        out = []
        for i in range(len(c)):
            if not inside[i]:
                out.append(None)
                continue
            y0, x0 = r0[i], c0[i]
            if not self.ok[y0:y0 + 2, x0:x0 + 2].all():
                out.append(None)
                continue
            fx, fy = c[i] - x0, r[i] - y0
            q = self.a[y0:y0 + 2, x0:x0 + 2]
            out.append(float(q[0, 0] * (1 - fx) * (1 - fy) + q[0, 1] * fx * (1 - fy) + q[1, 0] * (1 - fx) * fy + q[1, 1] * fx * fy))
        return out


def main(argv):
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    src, dem_path, out_osm, out_report = argv
    try:
        doc = read_osm(src)
        nodes = doc['nodes']
        elevation = Elevation(dem_path)

        def profile(seq):
            missing = [n for n in seq if n not in nodes]
            if missing:
                raise InputError(f'{src} lacks node {missing[0]}')
            pts, length = densify([(float(nodes[n][1]), float(nodes[n][0])) for n in seq])
            return elevation(pts), length

        report = orient(doc, profile)
    except InputError as err:
        print(f'orient.py: {err}', file=sys.stderr)
        return 2
    write_osm(out_osm, doc)
    with open(out_report, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    r, lf = report['runs'], report['lifts']
    print(f'orient: runs {r["ways"]} ways as {r["lines"]} lines, {r["oriented"]} with a direction '
          f'({len(r["ways_reversed"])} ways turned downhill), {len(r["without_direction"])} without; '
          f'lifts {lf["oriented"]} of {lf["ways"]} with a direction ({len(lf["ways_reversed"])} turned uphill)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

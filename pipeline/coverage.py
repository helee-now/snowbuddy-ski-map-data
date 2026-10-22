#!/usr/bin/env python3
"""Coverage report of one resort pack (ADR-036): does the box hold the resort, with room to spare?

Reads the GeoJSON written by normalize_osm.py, which holds exactly one ski-area feature: the resort's polygon (a
Polygon), or for a resort of several mountains a MultiPolygon with one member per listed polygon. The resort's terrain
is that feature plus every lift and in-bounds run (lines and run areas) within --resort-radius-km of the polygon's
bounding box (of any member's, for several mountains). All of it must lie inside the box, and the margin between the
box and that terrain must be at least --min-margin-km on every side (2 km by the box rule). Out-of-bounds runs are
listed but not required, because they may run far from the resort; for each, the report gives the zooms at which the
tiles hold all of it (drawn_whole_at) or only part of it (drawn_part_at). The tiles of a zoom are the ones touching
the box, as Planetiler and `pmtiles extract` cut them, so a run just beyond the box can sit in the larger low-zoom
tiles and still be cut from the max-zoom ones. Lifts and runs farther away are listed as other features: another venue
inside the Overpass margin that resorts.json does not list as a neighbour, such as Whistler Olympic Park. A listed
neighbour's lifts and runs never reach this report: normalize_osm.py leaves them out of the file.

Out-of-bounds runs named in the resort's `out_of_bounds_named` (resorts.json, with --resorts and --slug) are
required: each name must match at least one out-of-bounds run, drawn whole at every zoom (owner decision 2026-10-15:
they are shown, so the box holds them). A renamed, moved or deleted run in OSM therefore stops the build.

Usage: python3 -I coverage.py --features features.geojson --box W,S,E,N --out coverage.json \
           [--slug SLUG --key KEY --osm-base TIMESTAMP] [--resorts resorts.json] [--min-margin-km 2]
           [--resort-radius-km 2] [--zooms 11-14] [--report-only]
--zooms is the zoom range of the run layers (pack-schema.json: the piste layers' minzoom to the ski file's maxzoom).
Exit codes: 0 pass, 1 fail (0 with --report-only), 2 bad input.
"""
import argparse
import json
import math
import sys

EARTH_RADIUS_M = 6371008.8
SAMPLE_STEP_M = 10.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--features', required=True)
    ap.add_argument('--box', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--slug')
    ap.add_argument('--key')
    ap.add_argument('--osm-base')
    ap.add_argument('--resorts', help='resorts.json, for the out-of-bounds runs the resort names (needs --slug)')
    ap.add_argument('--min-margin-km', type=float, default=2.0)
    ap.add_argument('--resort-radius-km', type=float, default=2.0)
    ap.add_argument('--zooms', default='11-14', help='zoom range of the run layers, MIN-MAX')
    ap.add_argument('--report-only', action='store_true')
    a = ap.parse_args(argv)
    try:
        box = [float(v) for v in a.box.split(',')]
        assert len(box) == 4 and box[0] < box[2] and box[1] < box[3]
        zmin, zmax = (int(v) for v in a.zooms.split('-'))
        assert 0 <= zmin <= zmax <= 22
        with open(a.features, encoding='utf-8') as f:
            fc = json.load(f)
        named = []
        if a.resorts:
            with open(a.resorts, encoding='utf-8') as f:
                entry = next(r for r in json.load(f)['resorts'] if r['slug'] == a.slug)
            named = entry.get('out_of_bounds_named', [])
    except (ValueError, AssertionError, OSError, StopIteration) as err:
        print(f'coverage: bad input: {err}', file=sys.stderr)
        return 2
    report = coverage(fc, box, a.min_margin_km, a.resort_radius_km, range(zmin, zmax + 1), named)
    report = {'slug': a.slug, 'key': a.key, 'osm_base': a.osm_base, **report}
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    m = report['margins_km']
    print(f'coverage {a.slug or ""}: {"ok" if report["ok"] else "FAIL"}; margins W {m["west"]} S {m["south"]} '
          f'E {m["east"]} N {m["north"]} km; {report["counts"]["lifts"]} lifts, '
          f'{report["counts"]["runs_in_bounds"] + report["counts"]["run_areas_in_bounds"]} in-bounds runs, '
          f'{report["counts"]["runs_out_of_bounds"] + report["counts"]["run_areas_out_of_bounds"]} out of bounds')
    for p in report['problems']:
        print(f'  - {p}', file=sys.stderr)
    return 0 if report['ok'] or a.report_only else 1


def tile_footprint(box, z):
    """W, S, E, N of the tiles of zoom z that touch the box (the tiles Planetiler and `pmtiles extract` write)."""
    w, s, e, n = box
    size = 2 ** z

    def tx(lon):
        return (lon + 180.0) / 360.0 * size

    def ty(lat):
        return (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * size

    def lon(x):
        return x / size * 360.0 - 180.0

    def lat(y):
        return math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / size))))

    return [lon(math.floor(tx(w))), lat(math.ceil(ty(s))), lon(math.ceil(tx(e))), lat(math.floor(ty(n)))]


def coverage(fc, box, min_margin_km, resort_radius_km=2.0, zooms=range(11, 15), named=()):
    w, s, e, n = box
    k = EARTH_RADIUS_M * math.pi / 180.0
    kx = k * math.cos(math.radians((s + n) / 2.0))

    def dist_outside_m(lon, lat):
        dx = max(w - lon, 0.0, lon - e) * kx
        dy = max(s - lat, 0.0, lat - n) * k
        return math.hypot(dx, dy)

    def lines_of(geom):
        t, c = geom['type'], geom['coordinates']
        if t == 'LineString':
            return [c]
        if t == 'Polygon':
            return c
        if t == 'MultiPolygon':
            return [ring for poly in c for ring in poly]
        if t == 'Point':
            return [[c]]
        raise ValueError(f'unexpected geometry {t}')

    def outside(geom):
        """(max distance outside the box in m, length outside in m) over the feature's lines or outline."""
        far = out_len = 0.0
        for line in lines_of(geom):
            for lon, lat in line:
                far = max(far, dist_outside_m(lon, lat))
            for (x1, y1), (x2, y2) in zip(line, line[1:]):
                seg = math.hypot((x2 - x1) * kx, (y2 - y1) * k)
                steps = max(1, int(math.ceil(seg / SAMPLE_STEP_M)))
                for i in range(steps):
                    t = (i + 0.5) / steps
                    if dist_outside_m(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t) > 0.0:
                        out_len += seg / steps
        return far, out_len

    footprints = {z: tile_footprint(box, z) for z in zooms}

    def share_inside(geom, b):
        """Share of the feature's lines (or outline) inside the box b, sampled every SAMPLE_STEP_M metres."""
        bw, bs, be, bn = b
        total = inside = 0.0
        for line in lines_of(geom):
            for (x1, y1), (x2, y2) in zip(line, line[1:]):
                seg = math.hypot((x2 - x1) * kx, (y2 - y1) * k)
                steps = max(1, int(math.ceil(seg / SAMPLE_STEP_M)))
                for i in range(steps):
                    t = (i + 0.5) / steps
                    x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
                    total += seg / steps
                    if bw <= x <= be and bs <= y <= bn:
                        inside += seg / steps
        return inside / total if total else 0.0

    def drawn_at(geom):
        shares = {z: share_inside(geom, fp) for z, fp in footprints.items()}
        return {'drawn_whole_at': [z for z, v in shares.items() if v >= 1.0],
                'drawn_part_at': [z for z, v in shares.items() if 0.0 < v < 1.0]}

    def bbox_of(geom):
        pts = [pt for line in lines_of(geom) for pt in line]
        return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))

    areas = [f for f in fc['features'] if f['properties']['layer'] == 'ski_area']
    if len(areas) == 1:
        # The polygon's bounding box, all its rings; for a MultiPolygon (several mountains) each member's, so the
        # radius is measured from every mountain and not from one box around all of them.
        g = areas[0]['geometry']
        members = [{'type': 'Polygon', 'coordinates': c} for c in g['coordinates']] if g['type'] == 'MultiPolygon' else [g]
        rx, ry = resort_radius_km * 1000.0 / kx, resort_radius_km * 1000.0 / k
        near = []
        for m in members:
            aw, as_, ae, an = bbox_of(m)
            near.append((aw - rx, as_ - ry, ae + rx, an + ry))
    else:
        near = None

    def is_resort(geom):
        if near is None:
            return True
        fw, fs, fe, fn = bbox_of(geom)
        return any(not (fe < b[0] or fw > b[2] or fn < b[1] or fs > b[3]) for b in near)

    counts = {'lifts': 0, 'runs_in_bounds': 0, 'run_areas_in_bounds': 0, 'runs_out_of_bounds': 0,
              'run_areas_out_of_bounds': 0, 'lift_stations': 0, 'ski_area': 0, 'other_lifts_and_runs': 0}
    length_km = {'lifts': 0.0, 'runs_in_bounds': 0.0, 'runs_out_of_bounds': 0.0}
    lifts_outside, runs_outside, oob, others, problems = [], [], [], [], []
    ext = [math.inf, math.inf, -math.inf, -math.inf]

    def grow(geom):
        for line in lines_of(geom):
            for lon, lat in line:
                ext[0], ext[1] = min(ext[0], lon), min(ext[1], lat)
                ext[2], ext[3] = max(ext[2], lon), max(ext[3], lat)

    for f in fc['features']:
        p, g = f['properties'], f['geometry']
        layer = p['layer']
        if layer == 'ski_area':
            counts['ski_area'] += 1
            grow(g)
            far, _ = outside(g)
            if far > 0.0:
                problems.append(f'the ski-area polygon {p["osm"]} reaches {round(far)} m outside the box')
        elif layer in ('lift', 'piste', 'piste_area') and not p.get('out_of_bounds') and not is_resort(g):
            counts['other_lifts_and_runs'] += 1
            far, out_len = outside(g)
            others.append({'osm': p['osm'], 'layer': layer, 'name': p.get('name'),
                           'kind': p.get('kind') or p.get('type'), 'inside_box': far == 0.0})
        elif layer == 'lift':
            counts['lifts'] += 1
            length_km['lifts'] += p.get('length_m', 0) / 1000.0
            grow(g)
            far, out_len = outside(g)
            if far > 0.0:
                lifts_outside.append({'osm': p['osm'], 'name': p.get('name'), 'kind': p.get('kind'),
                                      'max_outside_m': round(far), 'length_outside_m': round(out_len)})
        elif layer in ('piste', 'piste_area'):
            area = layer == 'piste_area'
            far, out_len = outside(g)
            if p.get('out_of_bounds'):
                counts['run_areas_out_of_bounds' if area else 'runs_out_of_bounds'] += 1
                length_km['runs_out_of_bounds'] += p.get('length_m', 0) / 1000.0
                oob.append({'osm': p['osm'], 'name': p.get('name'), 'difficulty': p.get('difficulty'),
                            **({'area_m2': p.get('area_m2')} if area else {'length_m': p.get('length_m')}),
                            'inside_box': far == 0.0, **drawn_at(g)})
                continue
            counts['run_areas_in_bounds' if area else 'runs_in_bounds'] += 1
            length_km['runs_in_bounds'] += p.get('length_m', 0) / 1000.0
            grow(g)
            if far > 0.0:
                runs_outside.append({'osm': p['osm'], 'name': p.get('name'), 'difficulty': p.get('difficulty'),
                                     'max_outside_m': round(far), 'length_outside_m': round(out_len)})
        elif layer == 'lift_station':
            counts['lift_stations'] += 1

    all_zooms = list(footprints)
    for name in named:
        runs = [r for r in oob if r['name'] == name]
        if not runs:
            problems.append(f'the named out-of-bounds run {name!r} is not in the data (renamed or deleted in OSM?)')
        for r in runs:
            if r['drawn_whole_at'] != all_zooms:
                problems.append(f'the named out-of-bounds run {name!r} ({r["osm"]}) is not drawn whole at every zoom '
                                f'(whole at {r["drawn_whole_at"]}): grow the box')
    if counts['ski_area'] != 1:
        problems.append(f'expected exactly one ski-area feature (a Polygon, or a MultiPolygon for several mountains), found {counts["ski_area"]}')
    if counts['lifts'] == 0:
        problems.append('no lifts')
    if counts['runs_in_bounds'] == 0:
        problems.append('no in-bounds runs')
    if lifts_outside:
        problems.append(f'{len(lifts_outside)} lift(s) reach outside the box')
    if runs_outside:
        problems.append(f'{len(runs_outside)} in-bounds run(s) reach outside the box')
    if math.isinf(ext[0]):
        margins = {'west': None, 'south': None, 'east': None, 'north': None}
    else:
        margins = {
            'west': round((ext[0] - w) * kx / 1000.0, 2), 'south': round((ext[1] - s) * k / 1000.0, 2),
            'east': round((e - ext[2]) * kx / 1000.0, 2), 'north': round((n - ext[3]) * k / 1000.0, 2),
        }
        for side, km in margins.items():
            if km < min_margin_km:
                problems.append(f'{side} margin {km} km is under {min_margin_km} km')
    return {
        'box': box,
        'min_margin_km': min_margin_km,
        'terrain_extent': None if math.isinf(ext[0]) else [round(v, 6) for v in ext],
        'margins_km': margins,
        'counts': counts,
        'length_km': {k2: round(v, 1) for k2, v in length_km.items()},
        'lifts_outside_box': lifts_outside,
        'runs_outside_box': runs_outside,
        'out_of_bounds_named': list(named),
        'out_of_bounds_runs': sorted(oob, key=lambda r: r['osm']),
        'tile_footprints': {str(z): [round(v, 6) for v in fp] for z, fp in footprints.items()},
        'resort_radius_km': resort_radius_km,
        'other_lifts_and_runs': sorted(others, key=lambda r: r['osm']),
        'problems': problems,
        'ok': not problems,
    }


if __name__ == '__main__':
    sys.exit(main())

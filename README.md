# SnowBuddy ski map data

Ski runs, lifts, ski-area boundaries and contour lines for the resort maps in the SnowBuddy app, published under the
**Open Database License (ODbL) 1.0** together with the method that makes them. SnowBuddy helps a group of skiers find
each other on the mountain; its resort maps work offline and draw this data on top of a base map.

The runs, lifts and ski areas come from **OpenStreetMap**. The contour lines come from public elevation models. This
repository holds the files the app ships, their build records, and the scripts that rebuild them.

| Resort | Ski file | OSM data of | Bytes | SHA-256 (all in `SHA256SUMS`) |
|---|---|---|---|---|
| Whistler Blackcomb | [`data/whistler-blackcomb-v2-ski.pmtiles`](data/whistler-blackcomb-v2-ski.pmtiles) | 2026-10-15 06:13:50 UTC | 872,075 | `0d3663fce69c1596…` |
| Big White | [`data/big-white-v1-ski.pmtiles`](data/big-white-v1-ski.pmtiles) | 2026-10-15 06:15:47 UTC | 160,253 | `ccb514d1eac053d2…` |
| Mammoth Mountain | [`data/mammoth-mountain-v1-ski.pmtiles`](data/mammoth-mountain-v1-ski.pmtiles) | 2026-10-15 06:16:51 UTC | 247,816 | `26210726f2cb2ed6…` |

| Resort | Box (W, S, E, N) | Ski-area boundary in OSM | Contours from |
|---|---|---|---|
| Whistler Blackcomb | -123.08, 49.98, -122.83, 50.17 | [way/474288286](https://www.openstreetmap.org/way/474288286) | NRCan MRDEM-30 DTM |
| Big White | -119.01, 49.68, -118.88, 49.78 | [way/476836855](https://www.openstreetmap.org/way/476836855) | NRCan MRDEM-30 DTM |
| Mammoth Mountain | -119.1, 37.59, -118.96, 37.68 | [way/682231907](https://www.openstreetmap.org/way/682231907) | USGS 3DEP 1/3 arc-second |

OpenStreetMap data of 2026-10-15: 06:13:50 UTC for Whistler Blackcomb, 06:15:47 UTC for Big White and 06:16:51 UTC for Mammoth Mountain. Built on 2026-10-15.

> **Not for navigation or safety decisions.** Run ratings come from OpenStreetMap and can differ from the resort's own
> signs and trail map. Lines marked out of bounds lie outside the resort boundary. Always follow the resort's signs,
> closures and ski patrol.

## What the files hold

Each `data/<key>-ski.pmtiles` is a [PMTiles](https://github.com/protomaps/PMTiles) v3 archive of Mapbox Vector Tiles,
zoom 9 to 14, gzip-compressed, cut to the resort's box (`resorts.json`). Layers and fields (`pack-schema.json`; boolean
fields are present only when true):

| Layer | Geometry | From zoom | Fields |
|---|---|---|---|
| `piste` | line | 11 | `type` (downhill, snow_park, playground, connection), `difficulty` (novice, easy, intermediate, advanced, expert, freeride, extreme, unknown), `ungroomed`, `gladed`, `park`, `out_of_bounds`, `name`, `ref` |
| `piste_area` | polygon | 11 | as `piste` |
| `lift` | line | 10 | `kind` (the OSM `aerialway` value), `name`, `ref`, `occupancy` |
| `lift_station` | point | 13 | `name` |
| `ski_area` | polygon | 9 | `name`: the resort's own boundary, chosen by its OSM id |
| `contour` | line | 11 (index), 14 (all) | `ele` in metres every 20 m, `idx` on every 100 m line |

How OpenStreetMap tags become these fields (`pipeline/normalize_osm.py`):

- Runs are ways and multipolygons with `piste:type` downhill, snow_park, playground or connection, plus snow parks and
  halfpipes tagged only `amenity=snow_park`, `leisure=snow_park` or `man_made=piste:halfpipe`. Name, rating,
  grooming and `patrolled` missing on a way are copied from the piste route relations it belongs to; when a way is on a
  downhill route and on a ski-touring or nordic one, the downhill route decides.
- `difficulty` is OSM's `piste:difficulty`; any other value becomes `unknown`. A rating is never guessed.
- `ungroomed` marks `piste:grooming` backcountry, mogul or no, glades, and freeride or extreme runs; `park` marks snow
  parks and halfpipes.
- Left out: nordic, ski-touring and snowshoe trails, winter hiking, sledding and sleigh trails, zip lines and goods
  lifts. Lifts are chosen by `aerialway` alone (lifecycle keys such as `proposed:aerialway` are ignored), and lift
  stations only within 100 m of a kept lift.
- Text is reduced to the characters the app's map fonts can draw (Unicode 0–1023 and 8192–8447).
- `resorts/<slug>.overrides.json` holds the corrections applied on top of OpenStreetMap, each with a reason and the OSM
  value it expects; when OpenStreetMap changes, the build stops, so a fix made in OSM is never overwritten silently.

### Run ratings

The `difficulty` values are OpenStreetMap's `piste:difficulty`. The app draws them with the North American signs:
novice and easy green, intermediate blue, advanced black, expert, freeride and extreme double black, snow parks orange,
`unknown` grey. **They can differ from the resort's own signs and trail map**, and OSM cannot express every resort's
levels. Always follow the resort's signs.

### Out-of-bounds runs

A run tagged `piste:grooming=backcountry` or `patrolled=no` (on the way, or on its route relation) that lies mostly
outside the resort's ski-area boundary is kept with `out_of_bounds=true`, together with the boundary itself, so a map
can draw it in a distinct style with a warning.
**These lines are outside the resort: not patrolled, not avalanche-controlled, and not a recommendation.** They are
published because they are in OpenStreetMap and skiers use them; going there needs avalanche training, equipment and
partners.

Each box (`resorts.json`) holds the resort's lifts and runs with at least 2 km to spare, and the out-of-bounds runs
listed in `out_of_bounds_named` whole at every zoom. Other out-of-bounds runs beyond the box are cut at its edge or left
out, like everything else there. The coverage reports (`data/<key>-coverage.json`) list every out-of-bounds run with the
zooms whose tiles hold all of it (`drawn_whole_at`) or part of it (`drawn_part_at`).

Out-of-bounds runs in the files (OpenStreetMap data of the dates above); Big White has none:

| Resort | Run | OSM | In the box | Whole at | In part at |
|---|---|---|---|---|---|
| Whistler Blackcomb | Body Bag Bowl (named) | [way/472098498](https://www.openstreetmap.org/way/472098498) | yes | z11–14 | – |
| Whistler Blackcomb | Chamonix Chutes (named) | [way/399343702](https://www.openstreetmap.org/way/399343702) | yes | z11–14 | – |
| Whistler Blackcomb | Chamonix Chutes (named) | [way/399343703](https://www.openstreetmap.org/way/399343703) | yes | z11–14 | – |
| Whistler Blackcomb | DOA (Down, Over, and Around) (named) | [way/292816606](https://www.openstreetmap.org/way/292816606) | yes | z11–14 | – |
| Whistler Blackcomb | Helm's Deep (named) | [way/1512378030](https://www.openstreetmap.org/way/1512378030) | yes | z11–14 | – |
| Whistler Blackcomb | Helm's Gate (named) | [way/1512364218](https://www.openstreetmap.org/way/1512364218) | yes | z11–14 | – |
| Whistler Blackcomb | Blackcomb Home Run | [way/254397022](https://www.openstreetmap.org/way/254397022) | yes | z11–14 | – |
| Whistler Blackcomb | Blackcomb Home Run | [way/1169399417](https://www.openstreetmap.org/way/1169399417) | yes | z11–14 | – |
| Whistler Blackcomb | Blackcomb Home Run | [way/1169399418](https://www.openstreetmap.org/way/1169399418) | yes | z11–14 | – |
| Whistler Blackcomb | East Knob | [way/360676440](https://www.openstreetmap.org/way/360676440) | no | z11–12 | – |
| Whistler Blackcomb | Rainbow North Glacier | [way/258224692](https://www.openstreetmap.org/way/258224692) | no | – | – |
| Whistler Blackcomb | The Bussy | [way/1512345297](https://www.openstreetmap.org/way/1512345297) | no | z11–12 | – |
| Whistler Blackcomb | (unnamed) | [way/140799449](https://www.openstreetmap.org/way/140799449) | yes | z11–14 | – |
| Whistler Blackcomb | (unnamed) | [way/258224688](https://www.openstreetmap.org/way/258224688) | no | z11–14 | – |
| Whistler Blackcomb | (unnamed) | [way/258224689](https://www.openstreetmap.org/way/258224689) | no | z11–14 | – |
| Whistler Blackcomb | (unnamed) | [way/258224690](https://www.openstreetmap.org/way/258224690) | yes | z11–14 | – |
| Whistler Blackcomb | (unnamed) | [way/258224691](https://www.openstreetmap.org/way/258224691) | no | z11–12 | z13–14 |
| Whistler Blackcomb | (unnamed) | [way/258224693](https://www.openstreetmap.org/way/258224693) | no | – | – |
| Whistler Blackcomb | (unnamed) | [way/258225077](https://www.openstreetmap.org/way/258225077) | yes | z11–14 | – |
| Whistler Blackcomb | (unnamed) | [way/258225078](https://www.openstreetmap.org/way/258225078) | yes | z11–14 | – |
| Whistler Blackcomb | (unnamed) | [way/360676746](https://www.openstreetmap.org/way/360676746) | no | z11–12 | – |
| Whistler Blackcomb | (unnamed) | [way/360676750](https://www.openstreetmap.org/way/360676750) | no | z11–12 | – |
| Whistler Blackcomb | (unnamed) | [way/376911842](https://www.openstreetmap.org/way/376911842) | no | z11–14 | – |
| Whistler Blackcomb | (unnamed) | [way/376911843](https://www.openstreetmap.org/way/376911843) | no | z11–14 | – |
| Mammoth Mountain | Hollywood Chute (named) | [way/1143796677](https://www.openstreetmap.org/way/1143796677) | yes | z11–14 | – |
| Mammoth Mountain | Red Cone Bowl (named) | [way/1143796676](https://www.openstreetmap.org/way/1143796676) | yes | z11–14 | – |

## Sources and licences

**OpenStreetMap.** Runs, lifts and ski areas are OpenStreetMap data, fetched with the Overpass API:

> Map data © OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0. openstreetmap.org/copyright

**Contour lines.** Contours every 20 m are computed from one elevation model per resort:

- **NRCan MRDEM-30 DTM** (30 m), for Whistler Blackcomb and Big White: Open Government Licence - Canada (https://open.canada.ca/en/open-government-licence-canada). Data: https://canelevation-dem.s3.ca-central-1.amazonaws.com/mrdem-30/mrdem-30-dtm.tif

  > Contains information licensed under the Open Government Licence – Canada (NRCan MRDEM-30). This product was in part produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. The organisations in charge of the Copernicus program by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30.

  Nothing here implies endorsement by Natural Resources Canada or the Government of Canada.

- **USGS 3DEP 1/3 arc-second** (10 m), for Mammoth Mountain: Public domain (U.S. Geological Survey) (https://www.usgs.gov/3d-elevation-program). Data: https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/

  > 3DEP data courtesy of the U.S. Geological Survey.

**In each file.** The archive metadata carries the licence, in `description` ("This database is made available under
the Open Database License 1.0: https://opendatacommons.org/licenses/odbl/1-0/"), and the credit as linked HTML, in
`attribution`:

- `whistler-blackcomb-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://open.canada.ca/en/open-government-licence-canada">Contains information licensed under the Open Government Licence &ndash; Canada</a> (NRCan MRDEM-30, produced using Copernicus WorldDEM-30 &copy; DLR e.V. 2010-2014 and &copy; Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved)`
- `big-white-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://open.canada.ca/en/open-government-licence-canada">Contains information licensed under the Open Government Licence &ndash; Canada</a> (NRCan MRDEM-30, produced using Copernicus WorldDEM-30 &copy; DLR e.V. 2010-2014 and &copy; Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved)`
- `mammoth-mountain-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`

## Licence

- **The ski data** (`data/`, `resorts.json`, `pack-schema.json`, `resorts/`) is made available under the Open Database
  License: https://opendatacommons.org/licenses/odbl/1-0/ (full text in [`LICENSE`](LICENSE)). It is a derivative of
  OpenStreetMap, which is also under the ODbL. The contour lines in the files are derived from the elevation models
  above, which keep their own terms (the Open Government Licence – Canada with the Copernicus notice, and the public
  domain for 3DEP); keep their notices with any copy.
- **The scripts** (`pipeline/`) are under the MIT License ([`pipeline/LICENSE`](pipeline/LICENSE)).

Using the data means crediting "© OpenStreetMap contributors" and the elevation sources, and sharing any adapted
database under the ODbL (see the licence for the details).

## How to rebuild

You need bash, Docker and python3; the [pmtiles CLI](https://github.com/protomaps/go-pmtiles) is used for
`pmtiles verify` when it is installed. No account or key.

```bash
bash pipeline/build-ski.sh all                                 # the published files, from the recorded OSM data
bash pipeline/build-ski.sh big-white --osm-date=current        # one resort, current OpenStreetMap data
bash pipeline/build-ski.sh whistler-blackcomb --osm-date=2026-10-15T06:13:50Z   # the data as it was then
```

The files land in `out/` with their coverage reports, and the script says whether each file is identical to the
published one. Per resort it:

1. checks the Planetiler profile against its examples (`pipeline/ski-overlay.yml`, `ski-overlay.spec.yml`);
2. asks the Overpass API once for the resort's box plus 0.04° of longitude and 0.02° of latitude
   (`pipeline/overpass.sh`, with backoff on busy servers). The answer is cached in `.cache/` with the query that made
   it, and reused only for the same query: the same box, date and selection. With `--osm-date` the query carries
   `[date:"…"]`. Overpass reports its current time in a date-pinned answer, so the date asked for is what the file
   records;
3. normalises the answer (`normalize_osm.py`), writes a PBF with the data timestamp in its header (osmium), and checks
   the box (`coverage.py`);
4. reads the needed blocks of the elevation model over HTTPS (`fetch-dem.sh`) and draws contours on a 10 m grid
   (`contours.sh`, GDAL);
5. builds the tiles with Planetiler (`ski-overlay.yml`).

The tools run in Docker images pinned by digest in `pipeline/lib.sh`: `ghcr.io/osgeo/gdal:ubuntu-small-3.13.3@sha256:64250faf833c06d4b21afce4c27190039ba7ab58d70f0eebc87cf77d929c0b40` and `ghcr.io/onthegomap/planetiler:0.10.2@sha256:cf32202dbc001a9ab4bc11534b642b13de3798179817da8558e567a3d13dd403`, plus osmium 1.18.0 built from `pipeline/docker/osmium` on a Debian image pinned by digest.

With the recorded OSM data and unchanged elevation models the rebuild is byte-identical to `data/`. The publishers can
update the elevation models (3DEP's "current" tiles in particular), and then the contours, and the file, differ.

The scripts come from the SnowBuddy app's repository, where they are tested and also build the rest of each map pack
(the base map and the hillshade, which are not published here); comments that mention `build-pack.sh`,
`tile_raster.py`, `write-packs.mjs` or `test/` refer to files there. `pack-schema.json` describes the whole pack, of
which this repository holds the ski file.

## Corrections

Errors in runs, lifts or names are best fixed in OpenStreetMap itself (https://www.openstreetmap.org); the next build
picks them up. A correction that cannot be made in OSM goes into the resort's overrides file with its reason.

## Disclaimer

The data is provided as is, without any warranty, as the licence says. It is not a substitute for the resort's maps,
signs, closures and patrol instructions, and it can be incomplete or out of date. Run ratings come from OpenStreetMap
and can differ from the resort's signs.

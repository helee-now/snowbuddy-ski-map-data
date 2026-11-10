# SnowBuddy ski map data

Ski runs, lifts, ski-area boundaries and contour lines for the resort maps in the SnowBuddy app, published under the
**Open Database License (ODbL) 1.0** together with the method that makes them. SnowBuddy helps a group of skiers find
each other on the mountain; its resort maps work offline and draw this data on top of a base map.

The runs, lifts and ski areas come from **OpenStreetMap**. The contour lines come from public elevation models. This
repository holds the files the app downloads, their build records, and the scripts that rebuild them.

| Resort | Ski file | OSM data of | Bytes | SHA-256 (all in `SHA256SUMS`) |
|---|---|---|---|---|
| Alta | [`data/alta-v1-ski.pmtiles`](data/alta-v1-ski.pmtiles) | 2026-11-04 09:06:36 UTC | 305,562 | `67128d0ad3671218…` |
| Arapahoe Basin | [`data/arapahoe-basin-v1-ski.pmtiles`](data/arapahoe-basin-v1-ski.pmtiles) | 2026-11-04 17:25:54 UTC | 186,656 | `911468482c42696c…` |
| Aspen Snowmass | [`data/aspen-snowmass-v2-ski.pmtiles`](data/aspen-snowmass-v2-ski.pmtiles) | 2026-10-22 06:51:06 UTC | 865,404 | `56080678da141fe7…` |
| Bear Mountain | [`data/bear-mountain-v1-ski.pmtiles`](data/bear-mountain-v1-ski.pmtiles) | 2026-10-29 08:00:11 UTC | 107,809 | `8ef8a1b2cb17e879…` |
| Beaver Creek | [`data/beaver-creek-v1-ski.pmtiles`](data/beaver-creek-v1-ski.pmtiles) | 2026-11-04 17:50:18 UTC | 328,106 | `7e3ee1790b5019e0…` |
| Big Bear Mountain Resort | [`data/big-bear-mountain-resort-v2-ski.pmtiles`](data/big-bear-mountain-resort-v2-ski.pmtiles) | 2026-10-22 06:41:51 UTC | 149,841 | `efe20319e7bac54f…` |
| Big Sky | [`data/big-sky-v1-ski.pmtiles`](data/big-sky-v1-ski.pmtiles) | 2026-11-10 08:03:59 UTC | 448,182 | `33b313fa4abbfbba…` |
| Big White | [`data/big-white-v3-ski.pmtiles`](data/big-white-v3-ski.pmtiles) | 2026-10-15 06:15:47 UTC | 159,044 | `2441855b7379ad42…` |
| Breckenridge | [`data/breckenridge-v1-ski.pmtiles`](data/breckenridge-v1-ski.pmtiles) | 2026-11-04 17:06:45 UTC | 223,181 | `31d09c98c5c2004e…` |
| Brighton | [`data/brighton-v2-ski.pmtiles`](data/brighton-v2-ski.pmtiles) | 2026-10-22 06:47:58 UTC | 168,044 | `a3c2201ad03cdc02…` |
| Copper Mountain | [`data/copper-mountain-v1-ski.pmtiles`](data/copper-mountain-v1-ski.pmtiles) | 2026-11-04 17:16:51 UTC | 207,767 | `258a5362af386f61…` |
| Crested Butte | [`data/crested-butte-v1-ski.pmtiles`](data/crested-butte-v1-ski.pmtiles) | 2026-11-10 07:59:59 UTC | 183,843 | `8193e5b5054075e0…` |
| Deer Valley | [`data/deer-valley-v2-ski.pmtiles`](data/deer-valley-v2-ski.pmtiles) | 2026-10-22 06:50:06 UTC | 349,533 | `9abd659e02893978…` |
| Diamond Peak | [`data/diamond-peak-v1-ski.pmtiles`](data/diamond-peak-v1-ski.pmtiles) | 2026-10-31 22:06:49 UTC | 124,662 | `4b38917f0833a8b8…` |
| Eldora | [`data/eldora-v1-ski.pmtiles`](data/eldora-v1-ski.pmtiles) | 2026-11-10 07:51:51 UTC | 105,971 | `4832b43b40a86d04…` |
| Heavenly | [`data/heavenly-v1-ski.pmtiles`](data/heavenly-v1-ski.pmtiles) | 2026-10-31 21:59:50 UTC | 265,008 | `17aea3dea47c7371…` |
| Jackson Hole | [`data/jackson-hole-v1-ski.pmtiles`](data/jackson-hole-v1-ski.pmtiles) | 2026-11-10 07:56:57 UTC | 246,586 | `22dbdf11efd1fbee…` |
| June Mountain | [`data/june-mountain-v1-ski.pmtiles`](data/june-mountain-v1-ski.pmtiles) | 2026-11-04 08:54:21 UTC | 122,216 | `b2e4e99274fff78d…` |
| Keystone | [`data/keystone-v1-ski.pmtiles`](data/keystone-v1-ski.pmtiles) | 2026-11-04 17:19:51 UTC | 260,604 | `47b7b72789bf3ab0…` |
| Kirkwood | [`data/kirkwood-v1-ski.pmtiles`](data/kirkwood-v1-ski.pmtiles) | 2026-10-31 22:17:06 UTC | 186,881 | `2aced16f47fb987f…` |
| Mammoth Mountain | [`data/mammoth-mountain-v3-ski.pmtiles`](data/mammoth-mountain-v3-ski.pmtiles) | 2026-10-15 06:16:51 UTC | 220,545 | `c2ef3f52f95a4917…` |
| Mountain High | [`data/mountain-high-v1-ski.pmtiles`](data/mountain-high-v1-ski.pmtiles) | 2026-10-30 08:41:01 UTC | 197,923 | `c3bc80468f3cbba6…` |
| Northstar California | [`data/northstar-v1-ski.pmtiles`](data/northstar-v1-ski.pmtiles) | 2026-10-31 22:03:50 UTC | 148,604 | `ad70d089bc11a279…` |
| Palisades Tahoe | [`data/palisades-tahoe-v2-ski.pmtiles`](data/palisades-tahoe-v2-ski.pmtiles) | 2026-10-22 06:44:51 UTC | 387,907 | `1314525c3bc992da…` |
| Park City Mountain | [`data/park-city-mountain-v2-ski.pmtiles`](data/park-city-mountain-v2-ski.pmtiles) | 2026-10-22 06:50:06 UTC | 442,987 | `3b945de31b84783c…` |
| Sierra-at-Tahoe | [`data/sierra-at-tahoe-v1-ski.pmtiles`](data/sierra-at-tahoe-v1-ski.pmtiles) | 2026-10-31 22:06:49 UTC | 144,879 | `e78fc28eae1d83c8…` |
| Snow Summit | [`data/snow-summit-v1-ski.pmtiles`](data/snow-summit-v1-ski.pmtiles) | 2026-10-29 07:58:06 UTC | 88,758 | `e467ca780b28d23b…` |
| Snow Valley | [`data/snow-valley-v2-ski.pmtiles`](data/snow-valley-v2-ski.pmtiles) | 2026-10-22 06:42:51 UTC | 164,349 | `ba03bd7803225c79…` |
| Snowbasin | [`data/snowbasin-v1-ski.pmtiles`](data/snowbasin-v1-ski.pmtiles) | 2026-11-04 09:20:45 UTC | 279,131 | `29fd0239b333b9f8…` |
| Snowbird | [`data/snowbird-v1-ski.pmtiles`](data/snowbird-v1-ski.pmtiles) | 2026-11-04 09:12:38 UTC | 371,395 | `3aed69e80aba992d…` |
| Solitude | [`data/solitude-v1-ski.pmtiles`](data/solitude-v1-ski.pmtiles) | 2026-11-04 09:02:34 UTC | 209,897 | `bd92310ea22f58fc…` |
| Steamboat | [`data/steamboat-v2-ski.pmtiles`](data/steamboat-v2-ski.pmtiles) | 2026-10-22 06:46:56 UTC | 250,322 | `1a40436ff7ae6734…` |
| Sugar Bowl | [`data/sugar-bowl-v1-ski.pmtiles`](data/sugar-bowl-v1-ski.pmtiles) | 2026-10-31 22:19:59 UTC | 158,240 | `e603b8454f0ecb06…` |
| Sun Valley | [`data/sun-valley-v1-ski.pmtiles`](data/sun-valley-v1-ski.pmtiles) | 2026-11-10 08:18:05 UTC | 340,735 | `6afb69c2e3c83a41…` |
| Taos Ski Valley | [`data/taos-ski-valley-v1-ski.pmtiles`](data/taos-ski-valley-v1-ski.pmtiles) | 2026-11-10 08:06:59 UTC | 192,207 | `19d80f99af417125…` |
| Telluride | [`data/telluride-v1-ski.pmtiles`](data/telluride-v1-ski.pmtiles) | 2026-11-10 08:28:14 UTC | 255,880 | `3ba0b1778e27bbe7…` |
| Vail | [`data/vail-v1-ski.pmtiles`](data/vail-v1-ski.pmtiles) | 2026-11-04 17:25:54 UTC | 454,648 | `7599e11a31a63b27…` |
| Whistler Blackcomb | [`data/whistler-blackcomb-v4-ski.pmtiles`](data/whistler-blackcomb-v4-ski.pmtiles) | 2026-10-15 06:13:50 UTC | 838,922 | `ff73c9a03c7c9484…` |
| Winter Park | [`data/winter-park-v2-ski.pmtiles`](data/winter-park-v2-ski.pmtiles) | 2026-10-22 06:47:58 UTC | 249,857 | `5d52e67139620123…` |

| Resort | Box (W, S, E, N) | Ski-area boundary in OSM | Contours from |
|---|---|---|---|
| Alta | -111.68, 40.54, -111.57, 40.63 | [way/1023308077](https://www.openstreetmap.org/way/1023308077) | USGS 3DEP 1/3 arc-second |
| Arapahoe Basin | -105.92, 39.59, -105.83, 39.67 | [way/461239598](https://www.openstreetmap.org/way/461239598) | USGS 3DEP 1 m DEM |
| Aspen Snowmass | -107.01, 39.09, -106.78, 39.24 | [way/1144096092](https://www.openstreetmap.org/way/1144096092), [way/530531926](https://www.openstreetmap.org/way/530531926), [way/530531925](https://www.openstreetmap.org/way/530531925), [way/530538581](https://www.openstreetmap.org/way/530538581) | USGS 3DEP 1/3 arc-second |
| Bear Mountain | -116.9, 34.19, -116.82, 34.25 | [way/682224991](https://www.openstreetmap.org/way/682224991) | USGS 3DEP 1 m DEM |
| Beaver Creek | -106.61, 39.54, -106.46, 39.66 | [way/531009608](https://www.openstreetmap.org/way/531009608) | USGS 3DEP 1 m DEM |
| Big Bear Mountain Resort | -116.93, 34.19, -116.82, 34.26 | [way/1554647623](https://www.openstreetmap.org/way/1554647623), [way/682224991](https://www.openstreetmap.org/way/682224991) | USGS 3DEP 1 m DEM |
| Big Sky | -111.49, 45.22, -111.33, 45.34 | [way/1254863688](https://www.openstreetmap.org/way/1254863688) | USGS 3DEP 1/3 arc-second |
| Big White | -119.01, 49.68, -118.88, 49.78 | [way/476836855](https://www.openstreetmap.org/way/476836855) | NRCan MRDEM-30 DTM |
| Breckenridge | -106.14, 39.43, -106.02, 39.52 | [way/531005985](https://www.openstreetmap.org/way/531005985) | USGS 3DEP 1 m DEM |
| Brighton | -111.63, 40.56, -111.53, 40.62 | [way/682230007](https://www.openstreetmap.org/way/682230007) | USGS 3DEP 1 m DEM |
| Copper Mountain | -106.22, 39.43, -106.11, 39.52 | [way/531005986](https://www.openstreetmap.org/way/531005986) | USGS 3DEP 1 m DEM |
| Crested Butte | -107, 38.86, -106.89, 38.94 | [way/530521512](https://www.openstreetmap.org/way/530521512) | USGS 3DEP 1 m DEM |
| Deer Valley | -111.56, 40.56, -111.41, 40.67 | [way/682241434](https://www.openstreetmap.org/way/682241434) | USGS 3DEP 1/3 arc-second |
| Diamond Peak | -119.96, 39.22, -119.87, 39.29 | [way/467831000](https://www.openstreetmap.org/way/467831000) | USGS 3DEP 1/3 arc-second |
| Eldora | -105.64, 39.91, -105.55, 39.97 | [way/427517284](https://www.openstreetmap.org/way/427517284) | USGS 3DEP 1 m DEM |
| Heavenly | -119.97, 38.89, -119.85, 38.99 | [relation/12152028](https://www.openstreetmap.org/relation/12152028) | USGS 3DEP 1/3 arc-second |
| Jackson Hole | -110.91, 43.56, -110.79, 43.64 | [way/1074335726](https://www.openstreetmap.org/way/1074335726) | USGS 3DEP 1/3 arc-second |
| June Mountain | -119.12, 37.72, -119.03, 37.79 | [relation/14100275](https://www.openstreetmap.org/relation/14100275) | USGS 3DEP 1 m DEM |
| Keystone | -105.99, 39.51, -105.88, 39.63 | [way/531000583](https://www.openstreetmap.org/way/531000583) | USGS 3DEP 1 m DEM |
| Kirkwood | -120.12, 38.63, -120.01, 38.72 | [way/319472357](https://www.openstreetmap.org/way/319472357) | USGS 3DEP 1 m DEM |
| Mammoth Mountain | -119.1, 37.59, -118.96, 37.68 | [way/682231907](https://www.openstreetmap.org/way/682231907) | USGS 3DEP 1 m DEM |
| Mountain High | -117.73, 34.33, -117.65, 34.41 | derived from its lifts and runs (100 m) | USGS 3DEP 1 m DEM |
| Northstar California | -120.2, 39.21, -120.09, 39.3 | [relation/7095958](https://www.openstreetmap.org/relation/7095958) | USGS 3DEP 1 m DEM |
| Palisades Tahoe | -120.32, 39.09, -120.19, 39.24 | [relation/13336421](https://www.openstreetmap.org/relation/13336421), [relation/6704136](https://www.openstreetmap.org/relation/6704136) | USGS 3DEP 1 m DEM |
| Park City Mountain | -111.63, 40.59, -111.47, 40.72 | [way/918681867](https://www.openstreetmap.org/way/918681867) | USGS 3DEP 1/3 arc-second |
| Sierra-at-Tahoe | -120.13, 38.76, -120.02, 38.83 | [relation/9963336](https://www.openstreetmap.org/relation/9963336) | USGS 3DEP 1 m DEM |
| Snow Summit | -116.93, 34.2, -116.86, 34.26 | [way/1554647623](https://www.openstreetmap.org/way/1554647623) | USGS 3DEP 1 m DEM |
| Snow Valley | -117.07, 34.18, -117, 34.25 | [way/668577806](https://www.openstreetmap.org/way/668577806) | USGS 3DEP 1/3 arc-second |
| Snowbasin | -111.92, 41.16, -111.81, 41.24 | [way/1201185853](https://www.openstreetmap.org/way/1201185853) | USGS 3DEP 1/3 arc-second |
| Snowbird | -111.71, 40.52, -111.59, 40.61 | [way/1023308078](https://www.openstreetmap.org/way/1023308078) | USGS 3DEP 1/3 arc-second |
| Solitude | -111.65, 40.57, -111.56, 40.65 | [way/682230006](https://www.openstreetmap.org/way/682230006) | USGS 3DEP 1/3 arc-second |
| Steamboat | -106.85, 40.41, -106.71, 40.51 | [way/530998526](https://www.openstreetmap.org/way/530998526) | USGS 3DEP 1/3 arc-second |
| Sugar Bowl | -120.39, 39.26, -120.29, 39.34 | [relation/10326057](https://www.openstreetmap.org/relation/10326057) | USGS 3DEP 1 m DEM |
| Sun Valley | -114.45, 43.62, -114.3, 43.71 | [way/1244099443](https://www.openstreetmap.org/way/1244099443), [way/1244098768](https://www.openstreetmap.org/way/1244098768) | USGS 3DEP 1/3 arc-second |
| Taos Ski Valley | -105.49, 36.54, -105.41, 36.62 | [relation/13573224](https://www.openstreetmap.org/relation/13573224) | USGS 3DEP 1 m DEM |
| Telluride | -107.89, 37.86, -107.79, 37.96 | [way/528965906](https://www.openstreetmap.org/way/528965906) | USGS 3DEP 1 m DEM |
| Vail | -106.43, 39.53, -106.26, 39.67 | [way/531009607](https://www.openstreetmap.org/way/531009607) | USGS 3DEP 1 m DEM |
| Whistler Blackcomb | -123.08, 49.98, -122.83, 50.17 | [way/474288286](https://www.openstreetmap.org/way/474288286) | NRCan MRDEM-30 DTM |
| Winter Park | -105.84, 39.81, -105.72, 39.93 | [way/460246666](https://www.openstreetmap.org/way/460246666) | USGS 3DEP 1 m DEM |

OpenStreetMap data of 2026-11-04 09:06:36 UTC for Alta, 2026-11-04 17:25:54 UTC for Arapahoe Basin, 2026-10-22 06:51:06 UTC for Aspen Snowmass, 2026-10-29 08:00:11 UTC for Bear Mountain, 2026-11-04 17:50:18 UTC for Beaver Creek, 2026-10-22 06:41:51 UTC for Big Bear Mountain Resort, 2026-11-10 08:03:59 UTC for Big Sky, 2026-10-15 06:15:47 UTC for Big White, 2026-11-04 17:06:45 UTC for Breckenridge, 2026-10-22 06:47:58 UTC for Brighton, 2026-11-04 17:16:51 UTC for Copper Mountain, 2026-11-10 07:59:59 UTC for Crested Butte, 2026-10-22 06:50:06 UTC for Deer Valley, 2026-10-31 22:06:49 UTC for Diamond Peak, 2026-11-10 07:51:51 UTC for Eldora, 2026-10-31 21:59:50 UTC for Heavenly, 2026-11-10 07:56:57 UTC for Jackson Hole, 2026-11-04 08:54:21 UTC for June Mountain, 2026-11-04 17:19:51 UTC for Keystone, 2026-10-31 22:17:06 UTC for Kirkwood, 2026-10-15 06:16:51 UTC for Mammoth Mountain, 2026-10-30 08:41:01 UTC for Mountain High, 2026-10-31 22:03:50 UTC for Northstar California, 2026-10-22 06:44:51 UTC for Palisades Tahoe, 2026-10-22 06:50:06 UTC for Park City Mountain, 2026-10-31 22:06:49 UTC for Sierra-at-Tahoe, 2026-10-29 07:58:06 UTC for Snow Summit, 2026-10-22 06:42:51 UTC for Snow Valley, 2026-11-04 09:20:45 UTC for Snowbasin, 2026-11-04 09:12:38 UTC for Snowbird, 2026-11-04 09:02:34 UTC for Solitude, 2026-10-22 06:46:56 UTC for Steamboat, 2026-10-31 22:19:59 UTC for Sugar Bowl, 2026-11-10 08:18:05 UTC for Sun Valley, 2026-11-10 08:06:59 UTC for Taos Ski Valley, 2026-11-10 08:28:14 UTC for Telluride, 2026-11-04 17:25:54 UTC for Vail, 2026-10-15 06:13:50 UTC for Whistler Blackcomb and 2026-10-22 06:47:58 UTC for Winter Park. Built on 2026-11-04, 2026-10-23, 2026-10-29, 2026-11-05, 2026-11-10, 2026-10-31 and 2026-10-30.

> **Not for navigation or safety decisions.** Run ratings come from OpenStreetMap and can differ from the resort's own
> signs and trail map. Lines marked out of bounds lie outside the resort boundary. Always follow the resort's signs,
> closures and ski patrol.

## What the files hold

Each `data/<key>-ski.pmtiles` is a [PMTiles](https://github.com/protomaps/PMTiles) v3 archive of Mapbox Vector Tiles,
zoom 9 to 14, gzip-compressed, cut to the resort's box (`resorts.json`). Layers and fields (`pack-schema.json`; boolean
fields are present only when true):

| Layer | Geometry | From zoom | Fields |
|---|---|---|---|
| `piste` | line | 11 | `type` (downhill, snow_park, playground, connection), `difficulty` (novice, easy, intermediate, advanced, expert, freeride, extreme, unknown), `ungroomed`, `gladed`, `park`, `out_of_bounds`, `name`, `ref`, `rank` (1 trunk run, 2 other, 3 minor), `oriented` (runs downhill as drawn, checked against the elevation model) |
| `piste_area` | polygon | 11 | as `piste`, without `rank` and `oriented` |
| `lift` | line | 10 | `kind` (the OSM `aerialway` value), `name`, `ref`, `occupancy`, `oriented` (runs uphill as drawn) |
| `lift_station` | point | 13 | `name`; also the two ends of every lift, unnamed, where no station is within 40 m |
| `ski_area` | polygon | 9 | `name`: the resort's own boundary, chosen by its OSM id; for a resort of several mountains on one map, one multipolygon, the union of every mountain's polygon (`ski_area` lists their ids), named after the resort; for a resort with no `landuse=winter_sports` polygon in OpenStreetMap (`ski_area` is `"derived"`), one multipolygon derived from its own lifts and runs (below) |
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
  stations only within 100 m of a kept lift; each lift's two ends are stations too, unless one is within 40 m.
- Each file draws only its own resort. Another resort's ski area inside the box is listed under `neighbours` in
  `resorts.json`, with its OSM name, which the build checks. A lift, run or run area lying at least half in such a
  polygon is left out, with the stations of its lifts; one lying at least half in no polygon goes to the nearest
  polygon within 250 m, the resort's own or a neighbour's (when two are as near, to the one holding more of it, then to
  the resort), and is kept when none is that near. The neighbour's ground keeps its contours.
- A resort with no `landuse=winter_sports` polygon in OpenStreetMap (`ski_area` is `"derived"` in `resorts.json`) gets
  its ski area from its own lifts and runs: the kept lifts and downhill runs (lines, and run areas' outlines), after the
  overrides and the neighbour rule (there a feature is a neighbour's only when the neighbour's polygon holds at least
  half of it), each buffered by `ski_area_buffer_m` metres (100 when absent) in a local metric frame, unioned, every
  hole filled, groups whose buffers do not touch as polygons of their own, the outline simplified at 5 m. Nothing of
  such a resort is out of bounds by construction. The build stops when no lift or run is left to derive it from.
- `rank` (run lines): a named run is all its ways, their lengths added up, and belongs to the rating that holds most
  of its in-bounds length (easy, intermediate, advanced, expert with freeride and extreme, park, unrated). Rank 1 are,
  within each rating, the longest named runs with an in-bounds way, taken longest first until they make up half of
  that rating's named in-bounds run length; rank 3 are runs under 300 m (an unnamed way counts its own length); rank 2
  the others. For a resort of several mountains, a named run is the ways of that name on one mountain.
- Text is reduced to the characters the app's map fonts can draw (Unicode 0–1023 and 8192–8447).
- `resorts/<slug>.overrides.json` holds the corrections applied on top of OpenStreetMap, each with a reason and the OSM
  value it expects; when OpenStreetMap changes, the build stops, so a fix made in OSM is never overwritten silently.

### Directions

`pipeline/orient.py` reads the elevation model every 10 m along each run (smoothed over 20 m on each side). A run
whose ends are at least 10 m and 3% of its length apart, with climbs on the way down (rises of more than 3 m) adding
up to at most 30% of that drop, is written to run downhill (reversed if OpenStreetMap draws it uphill) and marked
`oriented`; others keep OpenStreetMap's direction without the mark. Ways of one run join end to end where no third
way with the same fields ends: marked ways only head to tail, unmarked ones either way round, so two runs flowing into
one junction never become one line. Lifts are decided the same way, uphill, with 5% instead of 3%. An arrow drawn
along a marked line follows the run's direction of travel; on unmarked lines the direction is not known.

### Run ratings

The `difficulty` values are OpenStreetMap's `piste:difficulty`. The app draws them with the North American signs:
novice and easy green, intermediate blue, advanced black, expert, freeride and extreme double black, snow parks orange,
`unknown` grey. **They can differ from the resort's own signs and trail map**, and OSM cannot express every resort's
levels. Always follow the resort's signs.

### Out-of-bounds runs

A run tagged `piste:grooming=backcountry` or `patrolled=no` (on the way, or on its route relation) that lies mostly
outside the resort's ski-area boundary (all of its mountains' polygons together, for a resort of several) is kept with
`out_of_bounds=true`, together with the boundary itself, so a map can draw it in a distinct style with a warning.
**These lines are outside the resort: not patrolled, not avalanche-controlled, and not a recommendation.** They are
published because they are in OpenStreetMap and skiers use them; going there needs avalanche training, equipment and
partners.

Each box (`resorts.json`) holds the resort's lifts and runs with at least 2 km to spare, and the out-of-bounds runs
listed in `out_of_bounds_named` whole at every zoom. Other out-of-bounds runs beyond the box are cut at its edge or left
out, like everything else there. The coverage reports (`data/<key>-coverage.json`) list every out-of-bounds run with the
zooms whose tiles hold all of it (`drawn_whole_at`) or part of it (`drawn_part_at`).

Out-of-bounds runs in the files (OpenStreetMap data of the dates above); Arapahoe Basin, Bear Mountain, Beaver Creek, Big Bear Mountain Resort, Big Sky, Big White, Breckenridge, Copper Mountain, Crested Butte, Deer Valley, Diamond Peak, Eldora, Heavenly, June Mountain, Keystone, Kirkwood, Mountain High, Northstar California, Sierra-at-Tahoe, Snow Summit, Snow Valley, Steamboat, Taos Ski Valley, Telluride, Vail and Winter Park have none:

| Resort | Run | OSM | In the box | Whole at | In part at |
|---|---|---|---|---|---|
| Alta | Suicide Chute | [way/1382646253](https://www.openstreetmap.org/way/1382646253) | yes | z11–14 | – |
| Aspen Snowmass | North Face of North Maroon Peak | [way/1228768990](https://www.openstreetmap.org/way/1228768990) | no | z11–13 | z14 |
| Aspen Snowmass | The Landry Line | [way/1228765519](https://www.openstreetmap.org/way/1228765519) | no | z11–13 | – |
| Brighton | Suicide Chute | [way/1382646253](https://www.openstreetmap.org/way/1382646253) | no | z11–13 | – |
| Jackson Hole | Cody Bowl (named) | [way/1297464831](https://www.openstreetmap.org/way/1297464831) | yes | z11–14 | – |
| Jackson Hole | Cody Bowl (named) | [way/1297464832](https://www.openstreetmap.org/way/1297464832) | yes | z11–14 | – |
| Jackson Hole | Rock Springs Bowl (named) | [way/318672230](https://www.openstreetmap.org/way/318672230) | yes | z11–14 | – |
| Jackson Hole | Rock Springs Bowl (named) | [way/1293309745](https://www.openstreetmap.org/way/1293309745) | yes | z11–14 | – |
| Jackson Hole | Rock Springs Bowl (named) | [way/1293309746](https://www.openstreetmap.org/way/1293309746) | yes | z11–14 | – |
| Jackson Hole | Rock Springs Bowl (named) | [way/1297464829](https://www.openstreetmap.org/way/1297464829) | yes | z11–14 | – |
| Jackson Hole | Four Shadows | [way/1297466409](https://www.openstreetmap.org/way/1297466409) | yes | z11–14 | – |
| Jackson Hole | No Shadows | [way/1297466411](https://www.openstreetmap.org/way/1297466411) | yes | z11–14 | – |
| Jackson Hole | Powder 8 | [way/1297466410](https://www.openstreetmap.org/way/1297466410) | yes | z11–14 | – |
| Jackson Hole | Pucker Face | [way/1297466408](https://www.openstreetmap.org/way/1297466408) | yes | z11–14 | – |
| Jackson Hole | (unnamed) | [way/1305149292](https://www.openstreetmap.org/way/1305149292) | yes | z11–14 | – |
| Jackson Hole | (unnamed) | [way/1305407651](https://www.openstreetmap.org/way/1305407651) | yes | z11–14 | – |
| Jackson Hole | (unnamed) | [way/1363957790](https://www.openstreetmap.org/way/1363957790) | yes | z11–14 | – |
| Mammoth Mountain | Hollywood Chute (named) | [way/1143796677](https://www.openstreetmap.org/way/1143796677) | yes | z11–14 | – |
| Mammoth Mountain | Red Cone Bowl (named) | [way/1143796676](https://www.openstreetmap.org/way/1143796676) | yes | z11–14 | – |
| Palisades Tahoe | Outer Outer (named) | [way/455183677](https://www.openstreetmap.org/way/455183677) | yes | z11–14 | – |
| Palisades Tahoe | Outer Outer Outer (named) | [way/455183676](https://www.openstreetmap.org/way/455183676) | yes | z11–14 | – |
| Park City Mountain | Suicide Chute | [way/1382646253](https://www.openstreetmap.org/way/1382646253) | no | z11–13 | – |
| Snowbasin | Blackbird | [way/1468799455](https://www.openstreetmap.org/way/1468799455) | yes | z11–14 | – |
| Snowbasin | Kiko | [way/1468805001](https://www.openstreetmap.org/way/1468805001) | yes | z11–14 | – |
| Snowbasin | Mt. Ogden Chute | [way/1468804997](https://www.openstreetmap.org/way/1468804997) | yes | z11–14 | – |
| Snowbasin | Porky Nose | [way/1468804999](https://www.openstreetmap.org/way/1468804999) | yes | z11–14 | – |
| Snowbasin | Race Start Chute 1 | [way/1468804998](https://www.openstreetmap.org/way/1468804998) | yes | z11–14 | – |
| Snowbasin | Race Start Chute 2 | [way/1550172148](https://www.openstreetmap.org/way/1550172148) | yes | z11–14 | – |
| Snowbasin | Race Start Chute 3 | [way/1550172149](https://www.openstreetmap.org/way/1550172149) | yes | z11–14 | – |
| Snowbird | Suicide Chute | [way/1382646253](https://www.openstreetmap.org/way/1382646253) | yes | z11–14 | – |
| Solitude | Suicide Chute | [way/1382646253](https://www.openstreetmap.org/way/1382646253) | no | z11–14 | – |
| Sugar Bowl | Lincoln East Face (named) | [way/1473727299](https://www.openstreetmap.org/way/1473727299) | yes | z11–14 | – |
| Sun Valley | Sunrise Bowl | [way/1340804770](https://www.openstreetmap.org/way/1340804770) | yes | z11–14 | – |
| Sun Valley | Sunrise Bowl | [way/1359433818](https://www.openstreetmap.org/way/1359433818) | yes | z11–14 | – |
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

## Sources and licences

**OpenStreetMap.** Runs, lifts and ski areas are OpenStreetMap data, fetched with the Overpass API:

> Map data © OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0. openstreetmap.org/copyright

**Contour lines.** Contours every 20 m are computed from one elevation model per resort:

- **USGS 3DEP 1/3 arc-second** (10 m), for Alta, Aspen Snowmass, Big Sky, Deer Valley, Diamond Peak, Heavenly, Jackson Hole, Park City Mountain, Snow Valley, Snowbasin, Snowbird, Solitude, Steamboat and Sun Valley: Public domain (U.S. Geological Survey) (https://www.usgs.gov/3d-elevation-program). Data: https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/

  > 3DEP data courtesy of the U.S. Geological Survey.

- **USGS 3DEP 1 m DEM** (1 m), for Arapahoe Basin, Bear Mountain, Beaver Creek, Big Bear Mountain Resort, Breckenridge, Brighton, Copper Mountain, Crested Butte, Eldora, June Mountain, Keystone, Kirkwood, Mammoth Mountain, Mountain High, Northstar California, Palisades Tahoe, Sierra-at-Tahoe, Snow Summit, Sugar Bowl, Taos Ski Valley, Telluride, Vail and Winter Park: Public domain (U.S. Geological Survey) (https://www.usgs.gov/3d-elevation-program). Data: https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/

  > 3DEP data courtesy of the U.S. Geological Survey.

- **NRCan MRDEM-30 DTM** (30 m), for Big White and Whistler Blackcomb: Open Government Licence - Canada (https://open.canada.ca/en/open-government-licence-canada). Data: https://canelevation-dem.s3.ca-central-1.amazonaws.com/mrdem-30/mrdem-30-dtm.tif

  > Contains information licensed under the Open Government Licence – Canada (NRCan MRDEM-30). This product was in part produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. The organisations in charge of the Copernicus program by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30.

  Nothing here implies endorsement by Natural Resources Canada or the Government of Canada.

**In each file.** The archive metadata carries the licence, in `description` ("This database is made available under
the Open Database License 1.0: https://opendatacommons.org/licenses/odbl/1-0/"), and the credit as linked HTML, in
`attribution`:

- `alta-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `arapahoe-basin-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `aspen-snowmass-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `bear-mountain-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `beaver-creek-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `big-bear-mountain-resort-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `big-sky-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `big-white-v3-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://open.canada.ca/en/open-government-licence-canada">Contains information licensed under the Open Government Licence &ndash; Canada</a> (NRCan MRDEM-30, produced using Copernicus WorldDEM-30 &copy; DLR e.V. 2010-2014 and &copy; Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved)`
- `breckenridge-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `brighton-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `copper-mountain-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `crested-butte-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `deer-valley-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `diamond-peak-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `eldora-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `heavenly-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `jackson-hole-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `june-mountain-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `keystone-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `kirkwood-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `mammoth-mountain-v3-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `mountain-high-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `northstar-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `palisades-tahoe-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `park-city-mountain-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `sierra-at-tahoe-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `snow-summit-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `snow-valley-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `snowbasin-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `snowbird-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `solitude-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `steamboat-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `sugar-bowl-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `sun-valley-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `taos-ski-valley-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `telluride-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `vail-v1-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`
- `whistler-blackcomb-v4-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://open.canada.ca/en/open-government-licence-canada">Contains information licensed under the Open Government Licence &ndash; Canada</a> (NRCan MRDEM-30, produced using Copernicus WorldDEM-30 &copy; DLR e.V. 2010-2014 and &copy; Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved)`
- `winter-park-v2-ski.pmtiles`: `<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>; contours: <a href="https://www.usgs.gov/3d-elevation-program">3DEP data courtesy of the U.S. Geological Survey</a>`

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
3. normalises the answer and ranks the runs (`normalize_osm.py`), and checks the box (`coverage.py`);
4. reads the needed blocks of the elevation model over HTTPS (`fetch-dem.sh`: a 1 m lidar model is found in its
   catalogue, The National Map's product API for 3DEP, and averaged onto a 4.8 m grid) and draws contours on a 10 m
   grid (`contours.sh`, GDAL; contours from lidar are smoothed with a 15 m Gaussian first, `dem.py`);
5. turns runs downhill and lifts uphill from the same elevation (`orient.py`, GDAL), and writes a PBF with the data
   timestamp in its header (osmium);
6. builds the tiles with Planetiler (`ski-overlay.yml`).

The tools run in Docker images pinned by digest in `pipeline/lib.sh`: `ghcr.io/osgeo/gdal:ubuntu-small-3.13.3@sha256:64250faf833c06d4b21afce4c27190039ba7ab58d70f0eebc87cf77d929c0b40` and `ghcr.io/onthegomap/planetiler:0.10.2@sha256:cf32202dbc001a9ab4bc11534b642b13de3798179817da8558e567a3d13dd403`, plus osmium 1.18.0 built from `pipeline/docker/osmium` on a Debian image pinned by digest.

With the recorded OSM data and unchanged elevation models the rebuild is byte-identical to `data/`. The publishers can
update the elevation models (3DEP's "current" 1/3″ tiles in particular, or a 3DEP project's 1 m tiles), and then the
contours, and the file, differ.

The scripts come from the SnowBuddy app's repository, where they are tested and also build the rest of each map pack
(the base map and the elevation file the app shades the relief from, which are not published here); comments that mention `build-pack.sh`,
`tile_raster.py`, `write-packs.mjs` or `test/` refer to files there. `pack-schema.json` describes the whole pack, of
which this repository holds the ski file.

## Corrections

Errors in runs, lifts or names are best fixed in OpenStreetMap itself (https://www.openstreetmap.org); the next build
picks them up. A correction that cannot be made in OSM goes into the resort's overrides file with its reason.

## Disclaimer

The data is provided as is, without any warranty, as the licence says. It is not a substitute for the resort's maps,
signs, closures and patrol instructions, and it can be incomplete or out of date. Run ratings come from OpenStreetMap
and can differ from the resort's signs.

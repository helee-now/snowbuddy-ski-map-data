#!/usr/bin/env python3
"""Elevation-window helpers for fetch-dem.sh and contours.sh (ADR-036). Runs inside the GDAL image (GDAL's Python
bindings and numpy); the array logic below needs numpy only, so the tests run it without GDAL.

  dem.py coverage <dem.tif> <W,S,E,N>
      prints JSON: the share of valid pixels in the whole window and in the box (pixel centres inside it), in percent
      with 3 decimals, and the exact number of missing pixels in each (window_missing_px, box_missing_px)
  dem.py fill <fine.tif> <coarse.tif> <out.tif>
      writes <out.tif>: the fine model where it has data, the coarse one (on the same grid) in its holes; prints JSON
      with the share of the window that was filled and the number of pixels filled
  dem.py smooth <in.tif> <out.tif> <sigma in pixels>
      writes <out.tif>: a Gaussian blur that ignores nodata (normalised convolution), so lidar micro-relief (boulders,
      road cuts, graded runs) does not make 20 m contours wiggle; nodata stays nodata

All rasters are single-band Float32 with nodata -32768 (fetch-dem.sh writes them so). `coverage` reads the box on a
Web Mercator (EPSG:3857) grid, the grid of the 1 m sources' windows.
"""
import json
import math
import sys

import numpy as np

NODATA = -32768.0
ORIGIN = 20037508.342789244  # half the Web Mercator world width in metres


def lonlat_to_merc(lon, lat):
    return lon / 180.0 * ORIGIN, math.asinh(math.tan(math.radians(lat))) / math.pi * ORIGIN


def box_pixel_window(gt, shape, box):
    """Rows and columns (half-open) of the pixels whose centres lie in the lon/lat box, on a north-up EPSG:3857 grid
    with geotransform gt."""
    x0, y1 = lonlat_to_merc(box[0], box[3])
    x1, y0 = lonlat_to_merc(box[2], box[1])
    cols = (gt[0] + (np.arange(shape[1]) + 0.5) * gt[1])
    rows = (gt[3] + (np.arange(shape[0]) + 0.5) * gt[5])
    c = np.nonzero((cols >= x0) & (cols <= x1))[0]
    r = np.nonzero((rows >= y0) & (rows <= y1))[0]
    if len(c) == 0 or len(r) == 0:
        raise ValueError('the box does not meet the raster')
    return int(r[0]), int(r[-1]) + 1, int(c[0]), int(c[-1]) + 1


def valid_mask(a, nodata=NODATA):
    return np.isfinite(a) & (a != nodata) & (a > -1000.0)


def coverage_of(a, window):
    """Valid share of the array and of window (r0, r1, c0, c1), in percent with 3 decimals, and the exact number of
    missing pixels in each. A share reads 100.0 with up to about 0.0005% missing (128 pixels of a Mammoth-sized
    window), so whether holes are filled is decided on the count (packlib.lidar_plan); the shares are for the record."""
    ok = valid_mask(a)
    r0, r1, c0, c1 = window
    box = ok[r0:r1, c0:c1]
    return {'window_pct': round(100.0 * float(ok.mean()), 3), 'box_pct': round(100.0 * float(box.mean()), 3),
            'window_missing_px': int(ok.size - np.count_nonzero(ok)), 'box_missing_px': int(box.size - np.count_nonzero(box))}


def fill_arrays(fine, coarse):
    """The fine model where valid, else the coarse one where valid, else nodata; the filled share in percent and the
    number of pixels filled."""
    fok = valid_mask(fine)
    cok = valid_mask(coarse)
    out = np.where(fok, fine, np.where(cok, coarse, NODATA)).astype(np.float32)
    filled = (~fok) & cok
    return out, round(100.0 * float(filled.mean()), 3), int(np.count_nonzero(filled))


def gaussian_kernel(sigma):
    radius = max(1, int(math.ceil(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    return k / k.sum()


def _convolve_axis(a, k, axis):
    r = (len(k) - 1) // 2
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode='constant')
    out = np.zeros_like(a)
    n = a.shape[axis]
    for i, w in enumerate(k):
        out += w * (p[i:i + n, :] if axis == 0 else p[:, i:i + n])
    return out


def smooth_array(a, sigma):
    """Gaussian blur of the valid pixels, normalised by the blurred validity so edges and holes do not pull values
    towards zero. sigma <= 0 returns the array unchanged."""
    if sigma <= 0:
        return a.astype(np.float32)
    ok = valid_mask(a)
    k = gaussian_kernel(sigma)
    num = _convolve_axis(_convolve_axis(np.where(ok, a, 0.0).astype(np.float64), k, 0), k, 1)
    den = _convolve_axis(_convolve_axis(ok.astype(np.float64), k, 0), k, 1)
    out = np.where(ok & (den > 1e-6), num / np.maximum(den, 1e-12), NODATA)
    return out.astype(np.float32)


def _read(path):
    from osgeo import gdal
    gdal.UseExceptions()
    ds = gdal.Open(path)
    band = ds.GetRasterBand(1)
    a = band.ReadAsArray().astype(np.float32)
    nd = band.GetNoDataValue()
    if nd is not None and nd != NODATA:
        a[a == nd] = NODATA
    return ds, a


def _write_like(ds, path, a):
    from osgeo import gdal
    drv = gdal.GetDriverByName('GTiff')
    out = drv.Create(path, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Float32,
                     options=['COMPRESS=DEFLATE', 'PREDICTOR=3', 'TILED=YES'])
    out.SetGeoTransform(ds.GetGeoTransform())
    out.SetProjection(ds.GetProjection())
    b = out.GetRasterBand(1)
    b.SetNoDataValue(NODATA)
    b.WriteArray(a)
    out.FlushCache()
    out = None


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == 'coverage':
            ds, a = _read(args[0])
            from osgeo import osr
            srs = osr.SpatialReference(wkt=ds.GetProjection())
            if srs.GetAuthorityCode(None) != '3857':
                raise ValueError(f'{args[0]} is not on a Web Mercator grid')
            box = [float(v) for v in args[1].split(',')]
            print(json.dumps(coverage_of(a, box_pixel_window(ds.GetGeoTransform(), a.shape, box))))
            return 0
        if cmd == 'fill':
            fds, fine = _read(args[0])
            cds, coarse = _read(args[1])
            if fine.shape != coarse.shape or fds.GetGeoTransform() != cds.GetGeoTransform():
                raise ValueError('the fine and coarse windows are not on the same grid')
            out, filled, filled_px = fill_arrays(fine, coarse)
            _write_like(fds, args[2], out)
            print(json.dumps({'filled_pct': filled, 'filled_px': filled_px}))
            return 0
        if cmd == 'smooth':
            ds, a = _read(args[0])
            _write_like(ds, args[1], smooth_array(a, float(args[2])))
            return 0
    except (IndexError, ValueError) as err:
        print(f'dem.py {cmd}: {err}', file=sys.stderr)
        return 2
    print(f'unknown command {cmd!r}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

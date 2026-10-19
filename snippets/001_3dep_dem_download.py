"""Download a USGS 3DEP DEM for any bounding box as a projected GeoTIFF.

The 3DEP elevation ImageServer resamples the best available lidar/IfSAR DEM to
whatever grid you ask for, but caps a single request at 8000 x 8000 px. This
script picks a UTM zone (or uses the CRS you give it), snaps the box to the
target resolution, requests it in 2000 px tiles (with retries), and writes one seamless GeoTIFF.

Example (Lafayette, LA at 10 m):
    python snippets/001_3dep_dem_download.py --bbox -92.12 30.15 -91.95 30.28 \
        --res 10 --out out/lafayette_dem_10m.tif

Data: USGS 3D Elevation Program, public domain.
"""

import argparse
import math
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box

SERVICE = ("https://elevation.nationalmap.gov/arcgis/rest/services/"
           "3DEPElevation/ImageServer/exportImage")
TILE = 2000  # px per side; the limit is 8000 but 4000 px tiles hit gateway timeouts
RETRIES = 3
NODATA = -9999.0


def fetch_tile(xmin, ymin, xmax, ymax, width, height, epsg):
    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "bboxSR": epsg,
        "imageSR": epsg,
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "F32",
        "noData": NODATA,
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    }
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(SERVICE, params=params, timeout=300)
            r.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt == RETRIES:
                raise
            print(f"  retry {attempt}/{RETRIES - 1} after: {e}")
            time.sleep(5 * attempt)
    if not r.content.startswith((b"II*\x00", b"MM\x00*")):
        raise RuntimeError(f"3DEP did not return a TIFF: {r.text[:300]}")
    with MemoryFile(r.content) as mem, mem.open() as src:
        return src.read(1)


def download_dem(bbox, res, out, epsg=None):
    aoi = gpd.GeoSeries([box(*bbox)], crs=4326)
    epsg = epsg or aoi.estimate_utm_crs().to_epsg()
    xmin, ymin, xmax, ymax = aoi.to_crs(epsg).total_bounds

    # snap outward to the resolution so pixels line up between runs
    xmin, ymin = math.floor(xmin / res) * res, math.floor(ymin / res) * res
    xmax, ymax = math.ceil(xmax / res) * res, math.ceil(ymax / res) * res
    width, height = round((xmax - xmin) / res), round((ymax - ymin) / res)

    dem = np.full((height, width), NODATA, dtype="float32")
    for row in range(0, height, TILE):
        for col in range(0, width, TILE):
            w, h = min(TILE, width - col), min(TILE, height - row)
            tx0 = xmin + col * res
            ty1 = ymax - row * res
            dem[row:row + h, col:col + w] = fetch_tile(
                tx0, ty1 - h * res, tx0 + w * res, ty1, w, h, epsg)
            print(f"  tile row {row}, col {col} ({w}x{h})")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    profile = dict(driver="GTiff", width=width, height=height, count=1,
                   dtype="float32", crs=f"EPSG:{epsg}", nodata=NODATA,
                   transform=from_origin(xmin, ymax, res, res),
                   compress="deflate", predictor=3, tiled=True)
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(dem, 1)

    valid = dem[dem != NODATA]
    print(f"Wrote {out}: {width}x{height} px, EPSG:{epsg}, "
          f"elevation {valid.min():.1f} to {valid.max():.1f} m")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bbox", nargs=4, type=float, required=True,
                   metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                   help="bounding box in decimal degrees (WGS84)")
    p.add_argument("--res", type=float, default=10, help="pixel size in metres")
    p.add_argument("--epsg", type=int, help="output CRS (default: local UTM zone)")
    p.add_argument("--out", default="out/dem.tif")
    a = p.parse_args()
    download_dem(a.bbox, a.res, a.out, a.epsg)

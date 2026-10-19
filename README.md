# gis-snippets

Small, self-contained GIS and remote sensing scripts, one task per file. Each
snippet runs on its own, uses open (mostly US federal) data, and has a usage
example in its docstring.

## Index

| # | Snippet | What it does | Stack |
|---|---------|--------------|-------|
| 001 | [3dep_dem_download](snippets/001_3dep_dem_download.py) | Tiled download of a USGS 3DEP DEM for any bbox, auto UTM, one GeoTIFF | rasterio, requests |

## Setup

```bash
pip install -r requirements.txt
```

Snippets marked **arcpy** need ArcGIS Pro and run through Pro's Python
(`propy.bat`). Everything else uses the open-source stack.

## License

MIT

"""Generic ArcGIS REST pager with an on-disk cache under data/raw/<name>/<offset>.json."""
import json
import time
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
TIMEOUT = 40
BBOX = (-117.97, 33.68, -117.83, 33.79)  # Santa Ana, WGS84 (xmin, ymin, xmax, ymax); build.py resets it per city
CACHE_PREFIX = ""  # "" for Santa Ana (original cache layout); "cities/<slug>" for other cities


def _get(url, params):
    """GET with one retry on timeout / connection error / ArcGIS error payload."""
    last = None
    for attempt in range(2):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(f"ArcGIS error: {data['error']}")
            return data
        except (requests.RequestException, ValueError, RuntimeError) as e:
            last = e
            time.sleep(1.0)
    raise RuntimeError(f"{url} failed after retry: {last}")


def get_json(name, url, params=None):
    """Fetch one JSON document (e.g. layer metadata), cached at data/raw/<name>/meta.json."""
    path = RAW / name / "meta.json"
    if path.exists():
        return json.loads(path.read_text())
    data = _get(url, dict(params or {}, f="json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def query(name, url, where="1=1", out_fields="*", page_size=2000, extra_params=None):
    """Page through an ArcGIS /query endpoint and return all features.

    Each page is cached at data/raw/<name>/<offset>.json; cached pages are reused, so a
    re-run works offline. Always passes f=json and outSR=4326.
    """
    feats, offset = [], 0
    folder = (RAW / CACHE_PREFIX / name) if CACHE_PREFIX else (RAW / name)
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        path = folder / f"{offset}.json"
        if path.exists():
            data = json.loads(path.read_text())
        else:
            params = {"where": where, "outFields": out_fields, "f": "json", "outSR": 4326,
                      "resultOffset": offset, "resultRecordCount": page_size}
            params.update(extra_params or {})
            data = _get(url, params)
            path.write_text(json.dumps(data))
            time.sleep(0.2)
        page = data.get("features", [])
        feats.extend(page)
        if not page or not (data.get("exceededTransferLimit") or len(page) >= page_size):
            break
        offset += len(page)
    return feats


def bbox_params(bbox=None):
    bbox = bbox or BBOX
    return {"geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "returnGeometry": "true",
            "geometryPrecision": 6}


def digits(s):
    return "".join(c for c in str(s or "") if c.isdigit())

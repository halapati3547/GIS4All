"""Pure-Python geometry helpers: ring centroid, point-in-polygon (multi-ring), haversine."""
import math


def ring_centroid(ring):
    """Mean of a ring's vertices (closing vertex dropped). Good enough for parcels."""
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def bbox_of(rings):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return (min(xs), min(ys), max(xs), max(ys))


class Polygon:
    """ArcGIS polygon (list of rings). Even-odd rule over all rings handles holes and multipart."""

    def __init__(self, rings, attrs=None):
        self.rings = [r for r in rings if len(r) >= 3]
        self.attrs = attrs or {}
        self.bbox = bbox_of(self.rings) if self.rings else (0, 0, -1, -1)

    def contains(self, x, y):
        b = self.bbox
        if not (b[0] <= x <= b[2] and b[1] <= y <= b[3]):
            return False
        return sum(point_in_ring(x, y, r) for r in self.rings) % 2 == 1


def polygons_from_features(features):
    return [Polygon(f["geometry"]["rings"], f.get("attributes"))
            for f in features if f.get("geometry", {}).get("rings")]


def first_containing(polys, x, y):
    for p in polys:
        if p.contains(x, y):
            return p
    return None


def haversine_m(lon1, lat1, lon2, lat2):
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Grid:
    """Simple lon/lat bucket index for 'any point within d metres' queries."""

    def __init__(self, points, cell_deg=0.005):
        self.cell = cell_deg
        self.buckets = {}
        for item in points:  # item = (lon, lat, payload)
            k = (int(item[0] // cell_deg), int(item[1] // cell_deg))
            self.buckets.setdefault(k, []).append(item)

    def near(self, lon, lat, dist_m):
        # 1 deg lat ~ 111 km; lon shrinks by cos(lat). Search enough cells to cover dist_m.
        span = int(math.ceil(dist_m / (111000 * math.cos(math.radians(lat)) * self.cell))) + 1
        cx, cy = int(lon // self.cell), int(lat // self.cell)
        out = []
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                for it in self.buckets.get((cx + dx, cy + dy), ()):
                    if haversine_m(lon, lat, it[0], it[1]) <= dist_m:
                        out.append(it)
        return out

from pipeline import geo

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
HOLE = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]]


def test_point_in_ring():
    assert geo.point_in_ring(5, 5, SQUARE)
    assert not geo.point_in_ring(15, 5, SQUARE)


def test_polygon_with_hole_and_bbox():
    p = geo.Polygon([SQUARE, HOLE])
    assert p.contains(1, 1)
    assert not p.contains(5, 5)  # inside the hole
    assert not p.contains(-1, 5)  # bbox pre-check
    assert p.bbox == (0, 0, 10, 10)


def test_multipart():
    far = [[20, 20], [30, 20], [30, 30], [20, 30], [20, 20]]
    p = geo.Polygon([SQUARE, far])
    assert p.contains(25, 25) and p.contains(5, 5) and not p.contains(15, 15)


def test_ring_centroid():
    assert geo.ring_centroid(SQUARE) == (5, 5)


def test_haversine_and_grid():
    d = geo.haversine_m(-117.87, 33.74, -117.87, 33.75)
    assert 1100 < d < 1120  # 0.01 deg lat ~ 1.11 km
    g = geo.Grid([(-117.87, 33.75, "a"), (-117.80, 33.75, "b")], 0.002)
    assert [x[2] for x in g.near(-117.87, 33.745, 805)] == ["a"]
    assert g.near(-117.87, 33.70, 805) == []

import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Not committed to the repo (23MB raw admin-1 boundaries). Download it first — see
# the "Regenerating india-map.json" section in README.md for the exact source URL.
SRC = ROOT / 'data' / 'source' / 'india-gadm-admin1-raw.geojson'
OUT = ROOT / 'india-map.json'

PILOT_NAME_TO_ID = {
    "Tamil Nadu": "tamil_nadu",
    "Delhi": "delhi",
    "Madhya Pradesh": "madhya_pradesh",
    "Assam": "assam",
    "Haryana": "haryana",
    "Telangana": "telangana",
    "Maharashtra": "maharashtra",
    "Gujarat": "gujarat",
    "Uttar Pradesh": "uttar_pradesh",
    "Bihar": "bihar",
    "Karnataka": "karnataka",
    "Jharkhand": "jharkhand",
}

with open(SRC) as f:
    gj = json.load(f)


def ring_area(ring):
    # shoelace, in degree^2 (fine for relative comparison)
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def dp_simplify(points, epsilon):
    if len(points) < 3:
        return points

    def perp_dist(pt, a, b):
        (x, y), (ax, ay), (bx, by) = pt, a, b
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(x - ax, y - ay)
        t = ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)
        px, py = ax + t * dx, ay + t * dy
        return math.hypot(x - px, y - py)

    def rdp(pts):
        if len(pts) < 3:
            return pts
        a, b = pts[0], pts[-1]
        max_d, idx = 0, 0
        for i in range(1, len(pts) - 1):
            d = perp_dist(pts[i], a, b)
            if d > max_d:
                max_d, idx = d, i
        if max_d > epsilon:
            left = rdp(pts[:idx + 1])
            right = rdp(pts[idx:])
            return left[:-1] + right
        else:
            return [a, b]

    return rdp(points)


def polygon_rings(geom):
    """Yield (ring, is_outer) lists of [lon,lat] for a Polygon or MultiPolygon,
    keeping only rings above an area threshold relative to the largest ring."""
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    all_rings = []
    for poly in polys:
        outer = poly[0]
        all_rings.append(outer)
    if not all_rings:
        return []
    max_area = max(ring_area(r) for r in all_rings)
    kept = [r for r in all_rings if ring_area(r) >= max_area * 0.03]
    return kept


# Collect pilot state rings (higher fidelity) and all-state rings (background, lower fidelity)
pilot_rings = {}
bg_rings = []
bounds = {"minlon": 999, "maxlon": -999, "minlat": 999, "maxlat": -999}

for feat in gj['features']:
    name = feat['properties']['NAME_1']
    geom = feat['geometry']
    rings = polygon_rings(geom)
    is_pilot = name in PILOT_NAME_TO_ID
    eps = 0.012 if is_pilot else 0.035
    simplified = [dp_simplify(r, eps) for r in rings]
    for r in simplified:
        for lon, lat in r:
            bounds['minlon'] = min(bounds['minlon'], lon)
            bounds['maxlon'] = max(bounds['maxlon'], lon)
            bounds['minlat'] = min(bounds['minlat'], lat)
            bounds['maxlat'] = max(bounds['maxlat'], lat)
    if is_pilot:
        pilot_rings[PILOT_NAME_TO_ID[name]] = {"name": name, "rings": simplified}
    else:
        bg_rings.append(simplified)

print("bounds", bounds)
print("pilot states found:", sorted(pilot_rings.keys()))
missing = set(PILOT_NAME_TO_ID.values()) - set(pilot_rings.keys())
print("missing:", missing)

# projection: equirectangular with longitude scaled by cos(mean latitude), fit to a
# VIEW_W x VIEW_H box preserving aspect ratio, with a small margin.
VIEW_W, VIEW_H, MARGIN = 1000, 1180, 20
mean_lat = (bounds['minlat'] + bounds['maxlat']) / 2
cos_lat = math.cos(math.radians(mean_lat))

lon_span = (bounds['maxlon'] - bounds['minlon']) * cos_lat
lat_span = (bounds['maxlat'] - bounds['minlat'])
avail_w, avail_h = VIEW_W - 2 * MARGIN, VIEW_H - 2 * MARGIN
scale = min(avail_w / lon_span, avail_h / lat_span)


def project(lon, lat):
    x = MARGIN + (lon - bounds['minlon']) * cos_lat * scale
    y = MARGIN + (bounds['maxlat'] - lat) * scale  # invert y (north = up)
    return round(x, 1), round(y, 1)


def ring_to_path(ring):
    pts = [project(lon, lat) for lon, lat in ring]
    d = "M" + " L".join(f"{x} {y}" for x, y in pts) + " Z"
    return d


out = {
    "view_w": VIEW_W, "view_h": VIEW_H,
    "pilot_states": {},
    "background_paths": [],
}

for sid, info in pilot_rings.items():
    out["pilot_states"][sid] = {
        "name": info["name"],
        "paths": [ring_to_path(r) for r in info["rings"] if len(r) >= 3],
    }

for rings in bg_rings:
    for r in rings:
        if len(r) >= 3:
            out["background_paths"].append(ring_to_path(r))

with open(OUT, 'w') as f:
    json.dump(out, f)

import os
print("output size:", os.path.getsize(OUT), "bytes")
for sid, s in out["pilot_states"].items():
    total_pts = sum(p.count(' L') + 1 for p in s["paths"])
    print(sid, "paths:", len(s["paths"]), "approx pts:", total_pts)

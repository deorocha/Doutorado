from shapely.geometry import shape
from pyproj import Geod

_GEOD = Geod(ellps="WGS84")


def validar_geometria(geojson_geom: dict) -> dict:
    """Valida polígono GeoJSON e retorna metadados úteis."""
    if not geojson_geom or geojson_geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("Geometria inválida: envie um Polygon ou MultiPolygon.")
    poly = shape(geojson_geom)
    if not poly.is_valid:
        raise ValueError("Polígono inválido (auto-interseção?). Redesenhe no mapa.")
    if poly.area <= 0:
        raise ValueError("Área zero — desenhe um polígono fechado.")
    area_m2, _ = _GEOD.geometry_area_perimeter(poly)
    if area_m2 <= 0:
        area_m2 = -area_m2
    centro = poly.centroid
    return {
        "geometry": poly.simplify(0.0001).__geo_interface__,
        "area_ha": area_m2 / 10_000,
        "lat": centro.y,
        "lon": centro.x,
    }


def utm_epsg(geom: dict) -> int:
    """EPSG do fuso UTM que contém o centróide do polígono.
    Brasil: 18S–25S → 32718..32725 (hemisfério sul).
    """
    c = shape(geom).centroid
    zona = int((c.x + 180) / 6) + 1
    return (32600 if c.y >= 0 else 32700) + zona

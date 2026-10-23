"""
NDVI/NDMI via Earth Search (Sentinel-2 L2A).

CONTEXTO: nesta máquina, GDAL HTTP (rasterio.open em URL) causa segfault
nativo (código -1073740791 / 0xC0000409) sem traceback Python. Isso derruba
o processo inteiro e o Streamlit cai.

SOLUÇÃO: baixar cada COG com requests (HTTP do Python, estável), salvar em
arquivo temporário local, abrir com rasterio a partir do disco (GDAL local,
estável) e apagar o arquivo depois. Processa banda a banda para conter
disco e memória. Uma cena por vez.

NOTA: todos os prints usam apenas ASCII para sobreviver a cp1252 (Windows).
"""
import os
import tempfile
import requests

from . import config


def _tem_satelite() -> bool:
    try:
        import rasterio  # noqa: F401
        import numpy     # noqa: F401
        return True
    except ImportError:
        return False


def _rfc3339(s: str, end_of_day: bool = False) -> str:
    s = s.strip()
    if "T" in s:
        return s if s.endswith("Z") else s + "Z"
    return f"{s}T23:59:59Z" if end_of_day else f"{s}T00:00:00Z"


def _href(asset):
    """Extrai URL de um asset STAC (string direto OU dict com 'href')."""
    if asset is None:
        return None
    if isinstance(asset, str):
        return asset
    if isinstance(asset, dict):
        return asset.get("href")
    return None


def buscar_cenas(geojson_geom: dict, inicio: str, fim: str, max_nuvem: int = None):
    """Busca Sentinel-2 L2A no Earth Search. Tenta coleções em ordem."""
    if max_nuvem is None:
        max_nuvem = getattr(config, "MAX_NUVEM_DEFAULT", 40)

    intervalo = f"{_rfc3339(inicio)}/{_rfc3339(fim, end_of_day=True)}"

    for colecao in config.STAC_COLLECTIONS:
        payload = {
            "collections": [colecao],
            "intersects": geojson_geom,
            "datetime": intervalo,
            "query": {"eo:cloud_cover": {"lt": max_nuvem}},
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
            "limit": 20,
        }
        r = requests.post(f"{config.STAC_URL}/search", json=payload,
                          timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            print(f"[stac] {colecao} HTTP {r.status_code}: {r.text[:200]}")
            continue
        feats = r.json().get("features", [])
        if feats:
            print(f"[stac] {colecao}: {len(feats)} cenas em {intervalo}")
            return feats
    return []


def _baixar_cog(href: str, destino: str, timeout: int = 300) -> str:
    """Baixa um COG com requests (HTTP do Python, não GDAL)."""
    with requests.get(href, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        lido = 0
        with open(destino, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                lido += len(chunk)
        print(f"[stac]   {os.path.basename(destino)}: {lido/1e6:.1f} MB baixados")
    return destino


def _ler_banda_local(href: str, bounds_wgs84, out_shape, resampling_name: str, tmpdir: str):
    """
    Baixa a banda, abre localmente com rasterio, lê a janela do polígono e
    apaga o arquivo. Retorna (array float32, crs da cena).
    """
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.warp import transform_bounds
    from rasterio.enums import Resampling

    resampling = getattr(Resampling, resampling_name)
    tmp = os.path.join(tmpdir, os.path.basename(href))

    _baixar_cog(href, tmp)
    try:
        with rasterio.open(tmp) as src:
            b = transform_bounds("EPSG:4326", src.crs, *bounds_wgs84)
            win = from_bounds(*b, transform=src.transform)
            arr = src.read(
                1, window=win, out_shape=out_shape,
                resampling=resampling, boundless=True, fill_value=0,
            ).astype("float32")
            crs = src.crs
        return arr, crs
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def indices_talhao(item, geojson_geom: dict) -> dict:
    """NDVI/NDMI médio no polígono. Usa download via requests + rasterio local."""
    if not _tem_satelite():
        raise RuntimeError("rasterio/numpy nao instalados")

    import numpy as np
    from rasterio.features import geometry_mask
    from rasterio.transform import from_bounds as tf_from_bounds
    from rasterio.warp import transform_geom
    from shapely.geometry import shape

    assets = item["assets"]
    bands = {
        "red":    _href(assets.get("red")    or assets.get("B04")),
        "nir":    _href(assets.get("nir")    or assets.get("B08")),
        "swir16": _href(assets.get("swir16") or assets.get("B11")),
        "scl":    _href(assets.get("scl")    or assets.get("SCL")),
    }
    if not all(bands.values()):
        raise RuntimeError(
            f"Bandas ausentes na cena. Assets disponiveis: {sorted(assets.keys())}"
        )

    poly = shape(geojson_geom)
    bounds_wgs84 = poly.bounds
    SHAPE = (100, 100)

    with tempfile.TemporaryDirectory(prefix="irrigacerta_") as tmpdir:
        print(f"[stac] cena {item['id']} -> shape={SHAPE}")
        red, src_crs = _ler_banda_local(
            bands["red"], bounds_wgs84, SHAPE, "bilinear", tmpdir)
        nir, _ = _ler_banda_local(
            bands["nir"], bounds_wgs84, SHAPE, "bilinear", tmpdir)
        swir, _ = _ler_banda_local(
            bands["swir16"], bounds_wgs84, SHAPE, "bilinear", tmpdir)
        scl, _ = _ler_banda_local(
            bands["scl"], bounds_wgs84, SHAPE, "nearest", tmpdir)

    mask_scl = np.isin(scl.astype("int16"), [4, 5, 6])

    poly_src = shape(transform_geom("EPSG:4326", str(src_crs), poly.__geo_interface__))
    b_src = poly_src.bounds
    transform = tf_from_bounds(b_src[0], b_src[1], b_src[2], b_src[3],
                               SHAPE[1], SHAPE[0])
    mask_poly = geometry_mask(
        [poly_src.__geo_interface__],
        out_shape=SHAPE, transform=transform, invert=True,
    )

    valido = mask_scl & mask_poly
    n_val = int(valido.sum())

    # --- Diagnóstico detalhado quando nada sobrevive ao filtro ---
    if n_val == 0:
        in_poly = int(mask_poly.sum())
        scl_vals, counts = np.unique(scl.astype("int16"), return_counts=True)
        dist = {int(v): int(c) for v, c in zip(scl_vals, counts) if c > 0}
        print(f"[stac] {item['id']}: pixels no poligono={in_poly}, "
              f"classes SCL={dist} (4=veg,5=solo,6=agua,0=fora do tile,"
              f"8/9/10=nuvem)")
        raise RuntimeError(
            f"sem pixels validos no poligono (SCL dist={dist})"
        )

    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (nir - red) / (nir + red)
        ndmi = (nir - swir) / (nir + swir)

    print(f"[stac] ok: {n_val} pixels validos de {SHAPE[0]*SHAPE[1]}")
    return {
        "data": item["properties"]["datetime"][:10],
        "ndvi": float(np.nanmean(ndvi[valido])),
        "ndmi": float(np.nanmean(ndmi[valido])),
        "nuvem": item["properties"].get("eo:cloud_cover"),
        "n_validos": n_val,
    }


def get_indices_serie(
    talhao_id: str,
    geojson_geom: dict,
    inicio: str,
    fim: str,
    force: bool = False,
    max_nuvem: int = None,
):
    """
    force=False: NUNCA baixa dados, só lê cache.
    force=True:  chamado SÓ por botão explícito.

    IMPORTANTE: processa cenas ordenadas por nuvem crescente (mais claras
    primeiro), não por data. Isso maximiza a chance de achar pixels limpos
    sobre o polígono mesmo quando a cena mais recente está nublada.
    """
    from . import storage

    if not force:
        return storage.ler_cache("sat", talhao_id) or []

    if config.DEMO_MODE or not _tem_satelite():
        return []

    nuvem = max_nuvem if max_nuvem is not None else config.MAX_NUVEM_DEFAULT
    limite = int(getattr(config, "MAX_CENAS_PROCESSAR", 3))

    cenas = buscar_cenas(geojson_geom, inicio, fim, max_nuvem=nuvem)
    # Ordena por nuvem crescente — processar as mais limpas primeiro
    cenas_ordenadas = sorted(
        cenas, key=lambda c: c["properties"].get("eo:cloud_cover", 100.0)
    )
    print(f"[stac] {len(cenas)} cenas retornadas; "
          f"processando ate {limite} (mais limpas primeiro)")
    if cenas_ordenadas:
        top = [(c['properties']['datetime'][:10],
                round(c['properties'].get('eo:cloud_cover', 100), 2))
               for c in cenas_ordenadas[:limite]]
        print(f"[stac] cenas escolhidas: {top}")

    serie, falhas = [], []
    for cena in cenas_ordenadas[:limite]:
        try:
            serie.append(indices_talhao(cena, geojson_geom))
        except MemoryError:
            print(f"[stac] MemoryError em {cena['id']}; abortando restante")
            break
        except Exception as e:
            falhas.append(f"{cena.get('id')}: {type(e).__name__}: {e}")
            print(f"[stac] falha em {cena.get('id')}: {type(e).__name__}: {e}")

    serie.sort(key=lambda x: x["data"])
    if serie:
        storage.salvar_cache("sat", talhao_id, serie)
    return serie


def get_indices_serie(
    talhao_id: str,
    geojson_geom: dict,
    inicio: str,
    fim: str,
    force: bool = False,
    max_nuvem: int = None,
):
    """
    force=False: NUNCA baixa dados, só lê cache.
    force=True:  chamado SÓ por botão explícito.
    """
    from . import storage

    if not force:
        return storage.ler_cache("sat", talhao_id) or []

    if config.DEMO_MODE or not _tem_satelite():
        return []

    nuvem = max_nuvem if max_nuvem is not None else config.MAX_NUVEM_DEFAULT
    limite = int(getattr(config, "MAX_CENAS_PROCESSAR", 2))

    cenas = buscar_cenas(geojson_geom, inicio, fim, max_nuvem=nuvem)
    print(f"[stac] {len(cenas)} cenas retornadas; processando ate {limite}")

    serie, falhas = [], []
    for cena in cenas[:limite]:
        try:
            serie.append(indices_talhao(cena, geojson_geom))
        except MemoryError:
            print(f"[stac] MemoryError em {cena['id']}; abortando restante")
            break
        except Exception as e:
            falhas.append(f"{cena.get('id')}: {type(e).__name__}: {e}")
            print(f"[stac] falha em {cena.get('id')}: {type(e).__name__}: {e}")

    serie.sort(key=lambda x: x["data"])
    if serie:
        storage.salvar_cache("sat", talhao_id, serie)
    return serie

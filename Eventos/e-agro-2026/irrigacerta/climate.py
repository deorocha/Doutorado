from datetime import date, timedelta
import requests

from . import config


def nasa_power_daily(lat: float, lon: float, inicio: date, fim: date) -> dict:
    """Série diária NASA POWER. Retorna {data_iso: {tmax, tmin, chuva, rh, ws, rs}}."""
    params = "PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN"
    url = (
        f"{config.NASA_POWER_URL}"
        f"?parameters={params}"
        f"&community=AG"
        f"&longitude={lon}&latitude={lat}"
        f"&start={inicio.strftime('%Y%m%d')}&end={fim.strftime('%Y%m%d')}"
        f"&format=JSON"
    )
    r = requests.get(url, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    dados = r.json()["properties"]["parameter"]

    chaves = list(dados.keys())
    datas = sorted(dados[chaves[0]].keys())

    out = {}
    for d in datas:
        linha = {k: dados[k][d] for k in chaves}
        if any(v == -999 for v in linha.values()):
            continue
        out[f"{d[0:4]}-{d[4:6]}-{d[6:8]}"] = {
            "tmax": linha["T2M_MAX"],
            "tmin": linha["T2M_MIN"],
            "chuva": max(0.0, linha["PRECTOTCORR"]),
            "rh": linha.get("RH2M"),
            "ws": linha.get("WS2M"),
            "rs": linha.get("ALLSKY_SFC_SW_DWN"),
        }
    return out


def open_meteo_forecast(lat: float, lon: float, dias: int = 7) -> dict:
    """Previsão diária Open-Meteo. Timezone automática a partir de lat/lon."""
    url = (
        f"{config.OPEN_METEO_URL}"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
        f"&forecast_days={dias}&timezone=auto"
    )
    r = requests.get(url, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    d = r.json()["daily"]
    out = {}
    for i, dia in enumerate(d["time"]):
        out[dia] = {
            "chuva": max(0.0, d["precipitation_sum"][i] or 0.0),
            "tmax": d["temperature_2m_max"][i],
            "tmin": d["temperature_2m_min"][i],
        }
    return out


def get_clima(talhao_id, lat, lon, data_plantio, force: bool = False):
    """
    Retorna (hist, prev, erro). erro=None quando OK.
    - force=True: ignora cache.
    - NASA POWER tem ~5–7 dias de latência; usamos fim = hoje - 7.
    """
    from . import storage

    if not force:
        cached = storage.ler_cache("clima", talhao_id)
        if cached:
            return cached["historico"], cached["previsao"], None

    if config.DEMO_MODE:
        return {}, {}, "modo demo ligado (IRRIGACERTA_DEMO_MODE=1)"

    fim = date.today() - timedelta(days=7)
    inicio = data_plantio - timedelta(days=5)
    if inicio > fim:
        return {}, {}, (
            f"data de plantio ({data_plantio}) muito recente; "
            f"NASA POWER só tem dados até {fim}"
        )

    try:
        hist = nasa_power_daily(lat, lon, inicio, fim)
    except Exception as e:
        return {}, {}, f"NASA POWER: {type(e).__name__}: {e}"

    try:
        prev = open_meteo_forecast(lat, lon)
    except Exception as e:
        return hist, {}, f"Open-Meteo: {type(e).__name__}: {e}"

    if hist:
        storage.salvar_cache("clima", talhao_id, {"historico": hist, "previsao": prev})
        return hist, prev, None

    return {}, prev, "NASA POWER respondeu sem dias válidos (latência ou -999)"

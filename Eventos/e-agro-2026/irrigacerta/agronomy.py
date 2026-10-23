from datetime import date, timedelta
import math

from . import config


def _ra(lat_deg: float, doy: int) -> float:
    """Radiação extraterrestre (MJ/m²/dia) — FAO-56 cap. 3."""
    lat = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * doy)
    delta = 0.409 * math.sin(2 * math.pi / 365 * doy - 1.39)
    ws_arg = -math.tan(lat) * math.tan(delta)
    ws_arg = max(min(ws_arg, 1.0), -1.0)
    ws = math.acos(ws_arg)
    return (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(lat) * math.sin(delta)
        + math.cos(lat) * math.cos(delta) * math.sin(ws)
    )


def eto_hargreaves(tmax: float, tmin: float, lat: float, dia: date) -> float:
    """ETo (mm/dia) por Hargreaves-Samani."""
    if tmax is None or tmin is None:
        return 0.0
    tmean = (tmax + tmin) / 2
    amplitude = max(tmax - tmin, 0.1)
    return 0.0023 * _ra(lat, dia.timetuple().tm_yday) * (tmean + 17.8) * math.sqrt(amplitude)


def kc_dia(cultura: str, dias_apos_plantio: int) -> float:
    """Kc FAO-56 com 4 estádios (ini → dev → mid → fim)."""
    p = config.KC.get(cultura)
    if not p:
        return 1.0
    d_ini, d_dev, d_mid, d_fim = p["dur"]
    kc_ini, kc_mid, kc_fim = p["ini"], p["mid"], p["fim"]

    d = dias_apos_plantio
    if d < 0:
        return 0.0
    if d < d_ini:
        return kc_ini
    d -= d_ini
    if d < d_dev:
        return kc_ini + (kc_mid - kc_ini) * (d / d_dev)
    d -= d_dev
    if d < d_mid:
        return kc_mid
    d -= d_mid
    if d < d_fim:
        return kc_mid + (kc_fim - kc_mid) * (d / d_fim)
    return kc_fim


def taw_mm(cultura: str, textura: str) -> float:
    return config.TAW_POR_METRO.get(textura, 120) * config.ZR_M.get(cultura, 0.5)


def balanco_hidrico(
    hist: dict,
    cultura: str,
    data_plantio: date,
    textura: str,
    lat: float,
):
    """
    Balanço tipo 'balde' FAO-56.
    Retorna lista de dicts por dia:
      {data, eto, kc, etc, chuva, dr, taw, raw, deficit}
    """
    taw = taw_mm(cultura, textura)
    raw = taw * config.DEPLETION_FRACTION

    datas = sorted(hist.keys())
    if not datas:
        return [], taw, raw

    dr = 0.0
    out = []
    for d_iso in datas:
        d = date.fromisoformat(d_iso)
        h = hist[d_iso]
        eto = eto_hargreaves(h["tmax"], h["tmin"], lat, d)
        dias = (d - data_plantio).days
        kc = kc_dia(cultura, dias)
        etc = eto * kc
        chuva = h["chuva"]

        dr = dr - chuva - 0.0 + etc           # irrigação tratada como 0 no histórico
        dr = max(0.0, min(dr, taw))
        out.append({
            "data": d_iso,
            "eto": round(eto, 2),
            "kc": round(kc, 3),
            "etc": round(etc, 2),
            "chuva": round(chuva, 2),
            "dr": round(dr, 2),
            "taw": round(taw, 2),
            "raw": round(raw, 2),
            "deficit": dr >= raw,
        })
    return out, taw, raw

"""
Diagnóstico das APIs do IrrigaCerta.
Rode com:  python -m scripts.diagnostico   (a partir da pasta app/)
"""
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from irrigacerta import config, storage


def sep(t):
    print("\n" + "=" * 60)
    print(t)
    print("=" * 60)


def testar_internet():
    sep("1. Conectividade")
    testes = [
        ("https://www.google.com", "Google"),
        ("https://api.open-meteo.com/v1/forecast?latitude=-9.4&longitude=-40.5&forecast_days=1", "Open-Meteo"),
        ("https://power.larc.nasa.gov/api/temporal/daily/point"
         "?parameters=T2M&community=AG&longitude=-40.5&latitude=-9.4"
         "&start=20260101&end=20260102&format=JSON", "NASA POWER"),
        ("https://earth-search.aws.element84.com/v1/", "Earth Search"),
    ]
    for url, nome in testes:
        try:
            r = requests.get(url, timeout=20)
            print(f"  {nome:15s} HTTP {r.status_code} ({len(r.content)} bytes)")
        except Exception as e:
            print(f"  {nome:15s} FALHOU: {type(e).__name__}: {e}")


def testar_nasa(lat, lon):
    sep("2. NASA POWER")
    from irrigacerta.climate import nasa_power_daily
    try:
        hist = nasa_power_daily(lat, lon, date.today() - timedelta(days=10), date.today())
        print(f"  dias retornados: {len(hist)}")
        for d in list(hist)[:3]:
            print(f"    {d}: {hist[d]}")
        if not hist:
            print("  ⚠ resposta vazia — verifique se lat/lon estão corretos")
    except Exception:
        traceback.print_exc()


def testar_meteo(lat, lon):
    sep("3. Open-Meteo")
    from irrigacerta.climate import open_meteo_forecast
    try:
        prev = open_meteo_forecast(lat, lon)
        print(f"  dias previstos: {len(prev)}")
        for d in list(prev)[:3]:
            print(f"    {d}: {prev[d]}")
    except Exception:
        traceback.print_exc()


def testar_stac(geom, talhao_id):
    sep("4. Earth Search (STAC)")
    from datetime import date, timedelta
    for colecao in config.STAC_COLLECTIONS:
        print(f"\n  coleção: {colecao}")
        payload = {
            "collections": [colecao],
            "intersects": geom,
            "datetime": f"{(date.today() - timedelta(days=60)).isoformat()}/{date.today().isoformat()}",
            "limit": 5,
        }
        try:
            r = requests.post(f"{config.STAC_URL}/search", json=payload, timeout=30)
            print(f"    HTTP {r.status_code}")
            if r.status_code != 200:
                print(f"    corpo: {r.text[:600]}")
                continue
            feats = r.json().get("features", [])
            print(f"    cenas: {len(feats)}")
            for f in feats[:2]:
                print(f"      {f['id']} {f['properties']['datetime'][:10]} "
                      f"nuvem={f['properties'].get('eo:cloud_cover')}")
                print(f"      assets: {sorted(f['assets'].keys())}")
        except Exception:
            traceback.print_exc()


def main():
    print(f"DEMO_MODE = {config.DEMO_MODE}")
    testar_internet()

    talhoes = storage.listar_talhoes()
    if not talhoes:
        print("\nSem talhões no banco.")
        return
    print(f"\n{len(talhoes)} talhão(ões):")
    for t in talhoes:
        print(f"  {t['id']}  {t['nome']}  lat={t['lat']:.4f} lon={t['lon']:.4f}")

    t = talhoes[0]
    print(f"\nTestando com: {t['nome']}")
    testar_nasa(t["lat"], t["lon"])
    testar_meteo(t["lat"], t["lon"])
    testar_stac(t["geometry"], t["id"])


if __name__ == "__main__":
    main()

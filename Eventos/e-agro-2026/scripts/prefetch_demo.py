"""
Pré-carrega clima (NASA POWER + Open-Meteo) e índices de satélite
(Earth Search) para TODOS os talhões no banco.

Rode com internet. Use antes do Demo Day, depois troque .env para
IRRIGACERTA_DEMO_MODE=1 para a demo 100% offline.

Uso:
    python -m scripts.prefetch_demo
"""
from datetime import date, timedelta

from irrigacerta import storage, climate, demo_data, config
from irrigacerta.stac import buscar_cenas, indices_talhao, _tem_satelite


def prefetch():
    storage.init_db()
    demo_data.ensure_demo_talhoes()

    for t in storage.listar_talhoes():
        print(f"\n=== {t['nome']} ({t['id']}) ===")
        d_plantio = date.fromisoformat(t["data_plantio"])

        # clima real — NASA POWER tem ~7 dias de latência, então fim = hoje-7
        try:
            fim_nasa = date.today() - timedelta(days=7)
            hist = climate.nasa_power_daily(
                t["lat"], t["lon"],
                d_plantio - timedelta(days=5),
                fim_nasa,
            )
            prev = climate.open_meteo_forecast(t["lat"], t["lon"], dias=7)
            storage.salvar_cache("clima", t["id"],
                                 {"historico": hist, "previsao": prev})
            print(f"  clima: {len(hist)} dias (até {fim_nasa}) + {len(prev)} previstos")
        except Exception as e:
            print(f"  clima FALHOU: {e}")

        # satélite (opcional)
        if not _tem_satelite():
            print("  satélite: rasterio/numpy não instalados — mantendo cache sintético")
            continue

        try:
            dias = getattr(config, "DIAS_SATELITE_DEFAULT", 90)
            cenas = buscar_cenas(
                t["geometry"],
                (date.today() - timedelta(days=dias)).isoformat(),
                date.today().isoformat(),
                max_nuvem=config.MAX_NUVEM_DEFAULT,
            )
            limite = int(getattr(config, "MAX_CENAS_PROCESSAR", 2))
            serie = []
            for c in cenas[:limite]:
                try:
                    serie.append(indices_talhao(c, t["geometry"]))
                except Exception as e:
                    print(f"  satélite falhou em {c.get('id')}: {e}")
            if serie:
                serie.sort(key=lambda x: x["data"])
                storage.salvar_cache("sat", t["id"], serie)
                print(f"  satélite: {len(serie)} cenas salvas")
            else:
                print("  satélite: nenhuma cena processada")
        except Exception as e:
            print(f"  satélite FALHOU: {e}")


if __name__ == "__main__":
    prefetch()

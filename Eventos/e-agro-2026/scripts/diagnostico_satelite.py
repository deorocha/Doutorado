"""
Diagnostica por que um talhão retorna sem cenas de satélite.

Uso: python -m scripts.diagnostico_satelite <talhao_id>
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from irrigacerta import storage, config, demo_data
from irrigacerta.stac import buscar_cenas, _tem_satelite


def main():
    if len(sys.argv) < 2:
        print("uso: python -m scripts.diagnostico_satelite <talhao_id>")
        return

    storage.init_db()
    demo_data.ensure_demo_talhoes()

    t = storage.obter_talhao(sys.argv[1])
    if not t:
        print(f"talhao {sys.argv[1]} nao encontrado")
        return

    print(f"Talhao: {t['nome']}")
    print(f"  lat={t['lat']:.4f} lon={t['lon']:.4f}")
    print(f"  area={t['area_ha']:.2f} ha")
    print(f"  DEMO_MODE={config.DEMO_MODE}")
    print(f"  tem_satelite={_tem_satelite()}")

    print("\n--- Variando limite de nuvem (60 dias) ---")
    for nuvem in [20, 40, 60, 80, 100]:
        cenas = buscar_cenas(
            t["geometry"],
            (date.today() - timedelta(days=60)).isoformat(),
            date.today().isoformat(),
            max_nuvem=nuvem,
        )
        nuvens = [c["properties"].get("eo:cloud_cover") for c in cenas[:5]]
        print(f"  max_nuvem={nuvem:3d}: {len(cenas):2d} cenas  "
              f"(nuvens amostra: {nuvens})")

    print("\n--- Variando período (max_nuvem=60) ---")
    for dias in [30, 60, 90, 180, 365]:
        cenas = buscar_cenas(
            t["geometry"],
            (date.today() - timedelta(days=dias)).isoformat(),
            date.today().isoformat(),
            max_nuvem=60,
        )
        print(f"  últimos {dias:3d} dias: {len(cenas):2d} cenas")

    print("\n--- Assets da cena mais recente ---")
    cenas = buscar_cenas(
        t["geometry"],
        (date.today() - timedelta(days=60)).isoformat(),
        date.today().isoformat(),
        max_nuvem=80,
    )
    if cenas:
        item = cenas[0]
        print(f"  cena: {item['id']}")
        print(f"  data: {item['properties']['datetime'][:10]}")
        print(f"  nuvem: {item['properties'].get('eo:cloud_cover')}%")
        for k in ("red", "nir", "swir16", "scl", "B04", "B08", "B11", "SCL"):
            if k in item["assets"]:
                href = item["assets"][k]
                href = href.get("href") if isinstance(href, dict) else href
                print(f"  {k}: {href[:80]}...")
    else:
        print("  NENHUMA cena encontrada nem com nuvem até 80%")
        print("  -> verifique se as coordenadas estão no hemisfério sul/Brasil")


if __name__ == "__main__":
    main()

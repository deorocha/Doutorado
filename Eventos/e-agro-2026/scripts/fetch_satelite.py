"""
Busca série de satélite para UM talhão. Roda em subprocesso separado.

AUTOSSUFICIENTE: cria o banco se não existir e garante os talhões de demo.
Força UTF-8 no stdout/stderr — evita UnicodeEncodeError em cp1252 (Windows).

Uso: python -m scripts.fetch_satelite <talhao_id> [dias]

Exit codes:
  0  ok
  2  argumentos inválidos
  3  talhão não encontrado
  4  rasterio/numpy não instalados
  5  nenhuma cena válida no período
  6  modo demo ativo (IRRIGACERTA_DEMO_MODE=1)
  1  erro inesperado
"""
import sys

# --- UTF-8 no stdout/stderr ANTES de qualquer outro import que possa printar ---
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from irrigacerta import storage, config, demo_data
from irrigacerta.stac import get_indices_serie, _tem_satelite, buscar_cenas


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: python -m scripts.fetch_satelite <talhao_id> [dias]")
        return 2

    talhao_id = sys.argv[1]
    dias = int(sys.argv[2]) if len(sys.argv) > 2 else getattr(config, "DIAS_SATELITE_DEFAULT", 90)

    # Garantir banco e talhões de demo (idempotente)
    storage.init_db()
    demo_data.ensure_demo_talhoes()

    print(f"[diag] DEMO_MODE = {config.DEMO_MODE}")
    print(f"[diag] MAX_CENAS_PROCESSAR = {getattr(config, 'MAX_CENAS_PROCESSAR', 'FALTA')}")
    print(f"[diag] _tem_satelite() = {_tem_satelite()}")
    print(f"[diag] talhao_id = {talhao_id}, dias = {dias}")

    if config.DEMO_MODE:
        print("ERRO: modo demo ligado no subprocesso. Falta .env na raiz?")
        return 6

    t = storage.obter_talhao(talhao_id)
    if not t:
        print(f"ERRO: talhao {talhao_id} nao encontrado")
        return 3

    if not _tem_satelite():
        print("ERRO: rasterio/numpy nao instalados - pip install rasterio numpy")
        return 4

    inicio = (date.today() - timedelta(days=dias)).isoformat()
    fim = date.today().isoformat()
    print(f"[diag] periodo = {inicio} -> {fim}")

    # Pre-checagem explicita (mensagem clara antes do download pesado)
    cenas = buscar_cenas(t["geometry"], inicio, fim,
                         max_nuvem=getattr(config, "MAX_NUVEM_DEFAULT", 40))
    print(f"[diag] buscar_cenas retornou {len(cenas)} cenas")
    if not cenas:
        print("ERRO: nenhuma cena no periodo para esse poligono")
        return 5

    serie = get_indices_serie(
        talhao_id, t["geometry"], inicio, fim, force=True,
    )
    print(f"RESULTADO: {len(serie)} cenas processadas e salvas em cache")
    for s in serie:
        print(
            f"  {s['data']}: NDVI={s['ndvi']:.3f} "
            f"NDMI={s['ndmi']:.3f} n_validos={s.get('n_validos','?')}"
        )

    return 0 if serie else 5


if __name__ == "__main__":
    sys.exit(main())

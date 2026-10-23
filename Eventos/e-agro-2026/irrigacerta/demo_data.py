"""
Talhões de demonstração com cache sintético — 100% offline.
Cenário A: tomate em déficit → recomenda irrigar.
Cenário B: milho com chuva prevista → recomenda aguardar.

ensure_demo_talhoes() é IDEMPOTENTE POR TALHÃO: excluir um dos dois não
derruba o restart. Se o talhão existe mas o cache de clima OU satélite
sumiu, o cache sintético correspondente é recriado.

ATENÇÃO — coordenadas:
As coordenadas abaixo são aproximações da região do Projeto Nilo Coelho
(Petrolina/PE). VERIFIQUE antes da demo com:

    python -m scripts.triagem_coords -9.3700,-40.6400 -9.3800,-40.6200

Se `veg%` vier < 30%, troque por outro ponto com vegetação real. Um
NDVI baixo (ex.: 0.07) no dashboard sinaliza área urbana / solo exposto,
não lavoura.
"""
from datetime import date, timedelta

from . import storage


DEMO = {
    "a1b2c3d4": {
        "nome": "Talhão A — Tomate (Nilo Coelho/PE)",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-40.6420, -9.3680], [-40.6380, -9.3680],
                [-40.6380, -9.3720], [-40.6420, -9.3720],
                [-40.6420, -9.3680],
            ]],
        },
        "area_ha": 4.2,
        "cultura": "tomate",
        "data_plantio": (date.today() - timedelta(days=70)).isoformat(),
        "textura_solo": "franco-arenoso",
        "sistema_irrigacao": "gotejamento",
        "vazao_mm_h": 5.5,
        "lat": -9.3700,
        "lon": -40.6400,
    },
    "e5f6a7b8": {
        "nome": "Talhão B — Milho (Nilo Coelho/PE)",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-40.6220, -9.3780], [-40.6180, -9.3780],
                [-40.6180, -9.3820], [-40.6220, -9.3820],
                [-40.6220, -9.3780],
            ]],
        },
        "area_ha": 6.0,
        "cultura": "milho",
        "data_plantio": (date.today() - timedelta(days=55)).isoformat(),
        "textura_solo": "franco",
        "sistema_irrigacao": "aspersao",
        "vazao_mm_h": 6.0,
        "lat": -9.3800,
        "lon": -40.6200,
    },
}


def _serie_historico(dias: int, chuva_base: float):
    """Histórico sintético. Tmax/Tmin fixos — só a chuva varia."""
    hoje = date.today()
    out = {}
    for i in range(dias, 0, -1):
        d = hoje - timedelta(days=i)
        chuva = max(0.0, chuva_base * (1 if i > dias * 0.7 else 0.2))
        out[d.isoformat()] = {
            "tmax": 33.0, "tmin": 22.0,
            "chuva": round(chuva, 2),
            "rh": 55, "ws": 2.0, "rs": 22.0,
        }
    return out


def _previsao(dias: int, chuva_dia: float):
    hoje = date.today()
    return {
        (hoje + timedelta(days=i)).isoformat(): {
            "chuva": chuva_dia, "tmax": 33.0, "tmin": 22.0,
        }
        for i in range(1, dias + 1)
    }


def _criar_cache_demo(tid: str):
    if tid == "a1b2c3d4":
        hist = _serie_historico(dias=60, chuva_base=0.0)
        prev = _previsao(dias=7, chuva_dia=0.0)
    else:
        hist = _serie_historico(dias=60, chuva_base=2.0)
        prev = _previsao(dias=7, chuva_dia=12.0)
    storage.salvar_cache("clima", tid, {"historico": hist, "previsao": prev})

    sat = []
    for i in range(6, 0, -1):
        sat.append({
            "data": (date.today() - timedelta(days=i * 10)).isoformat(),
            "ndvi": 0.72 - 0.03 * i if tid == "a1b2c3d4" else 0.68 + 0.01 * i,
            "ndmi": 0.25 - 0.04 * i if tid == "a1b2c3d4" else 0.30 + 0.02 * i,
            "nuvem": 5.0,
        })
    storage.salvar_cache("sat", tid, sat)


def ensure_demo_talhoes():
    """Idempotente POR TALHÃO e POR CACHE."""
    storage.init_db()
    for tid, dados in DEMO.items():
        if not storage.talhao_existe(tid):
            storage.criar_talhao(id=tid, **dados)
        # Se o cache de clima OU de satélite estiver faltando, recria ambos
        # (a função _criar_cache_demo escreve os dois de uma vez).
        if (storage.ler_cache("clima", tid) is None
                or storage.ler_cache("sat", tid) is None):
            _criar_cache_demo(tid)

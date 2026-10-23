import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS talhoes (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    geometry TEXT NOT NULL,
    area_ha REAL NOT NULL,
    cultura TEXT NOT NULL,
    data_plantio TEXT NOT NULL,
    textura_solo TEXT NOT NULL,
    sistema_irrigacao TEXT NOT NULL,
    vazao_mm_h REAL NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    criado_em TEXT NOT NULL
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.executescript(SCHEMA)


def criar_talhao(**kwargs) -> str:
    talhao_id = kwargs.pop("id", None) or uuid.uuid4().hex[:8]
    with _conn() as con:
        con.execute(
            """INSERT INTO talhoes
            (id, nome, geometry, area_ha, cultura, data_plantio,
             textura_solo, sistema_irrigacao, vazao_mm_h, lat, lon, criado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                talhao_id,
                kwargs["nome"],
                json.dumps(kwargs["geometry"]),
                kwargs["area_ha"],
                kwargs["cultura"],
                kwargs["data_plantio"],
                kwargs["textura_solo"],
                kwargs["sistema_irrigacao"],
                kwargs["vazao_mm_h"],
                kwargs["lat"],
                kwargs["lon"],
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return talhao_id


def listar_talhoes():
    with _conn() as con:
        rows = con.execute("SELECT * FROM talhoes ORDER BY criado_em").fetchall()
    return [dict(r) for r in rows]


def obter_talhao(talhao_id: str):
    with _conn() as con:
        row = con.execute("SELECT * FROM talhoes WHERE id=?", (talhao_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["geometry"] = json.loads(d["geometry"])
    return d


def talhao_existe(talhao_id: str) -> bool:
    return obter_talhao(talhao_id) is not None


def deletar_talhao(talhao_id: str) -> bool:
    """Remove o talhão e todos os caches associados (clima + satélite)."""
    with _conn() as con:
        cur = con.execute("DELETE FROM talhoes WHERE id=?", (talhao_id,))
        deletado = cur.rowcount > 0
    if deletado:
        for kind in ("clima", "sat"):
            apagar_cache(kind, talhao_id)
    return deletado


# ---------- cache de dados externos ----------

def cache_path(kind: str, talhao_id: str):
    return config.CACHE_DIR / f"{kind}_{talhao_id}.json"


def salvar_cache(kind: str, talhao_id: str, payload):
    with open(cache_path(kind, talhao_id), "w") as f:
        json.dump(payload, f, indent=2, default=str)


def ler_cache(kind: str, talhao_id: str):
    p = cache_path(kind, talhao_id)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def apagar_cache(kind: str, talhao_id: str) -> bool:
    p = cache_path(kind, talhao_id)
    if p.exists():
        p.unlink()
        return True
    return False

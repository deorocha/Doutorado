r"""
1. ambiente:
    python -m venv .venv && source .venv/bin/activate
    # Windows: .venv\Scripts\activate

2. instalar dependências
    pip install -r requirements.txt

3. (opcional) puxar dados reais para o cache — rode com internet
    python -m scripts.prefetch_demo

4. subir o app
    Windows (cmd):        set IRRIGACERTA_DEMO_MODE=0
    Windows (PowerShell): $env:IRRIGACERTA_DEMO_MODE="0"
    Linux/macOS:          export IRRIGACERTA_DEMO_MODE=0
    streamlit run app.py
5. limpar cache e arquivo de dados:
    rmdir /s /q data\cache
    del data\irrigacerta.db
"""

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import plotly.graph_objects as go

import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import pandas as pd

from irrigacerta import config, storage, geo, climate, agronomy, recommender, demo_data
from irrigacerta.stac import _tem_satelite

st.title("Hackathon - E-Agro 2026 - Recomendação de irrigação")

# Raiz do projeto — usada como cwd do subprocesso de satélite
PROJECT_ROOT = Path(__file__).resolve().parent

# Tradução dos códigos de saída do subprocesso de satélite
EXIT_CODES = {
    0: "OK",
    1: "erro inesperado — ver traceback no log abaixo",
    2: "argumentos inválidos",
    3: "talhão não encontrado",
    4: "rasterio/numpy não instalados — `pip install rasterio numpy`",
    5: f"nenhuma cena válida nos últimos {getattr(config, 'DIAS_SATELITE_DEFAULT', 60)} dias (verifique coordenadas e nuvem)",
    6: "modo demo ativo no subprocesso (.env ausente?)",
}

# ==========================================================================
# ESTILOS DE MAPA
# Cada estilo é uma lista de camadas (TileLayer). A primeira camada é o
# fundo; as seguintes são overlays (rótulos, fronteiras). Para Esri Híbrido,
# por exemplo, é satélite + rótulos.
# ==========================================================================
TILE_PROVIDERS = {
    # ---------------- Google (via mt1.google.com) ----------------
    "google_sat": {
        "nome": "Google · Satélite",
        "layers": [
            {"url": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
             "attr": "© Google", "overlay": False},
        ],
    },
    "google_hybrid": {
        "nome": "Google · Híbrido (satélite + nomes)",
        "layers": [
            {"url": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
             "attr": "© Google", "overlay": False},
        ],
    },
    "google_roads": {
        "nome": "Google · Ruas",
        "layers": [
            {"url": "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
             "attr": "© Google", "overlay": False},
        ],
    },
    "google_terrain": {
        "nome": "Google · Terreno",
        "layers": [
            {"url": "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
             "attr": "© Google", "overlay": False},
        ],
    },
    "google_night": {
        "nome": "Google · Noite (navegação)",
        "layers": [
            {"url": "https://mt1.google.com/vt/lyrs=n&x={x}&y={y}&z={z}",
             "attr": "© Google", "overlay": False},
        ],
    },

    # ---------------- Esri ----------------
    "esri_sat": {
        "nome": "Esri · Satélite",
        "layers": [
            {"url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
             "attr": "Tiles © Esri", "overlay": False},
        ],
    },
    "esri_hybrid": {
        "nome": "Esri · Híbrido (satélite + rótulos)",
        "layers": [
            {"url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
             "attr": "Tiles © Esri", "overlay": False},
            {"url": "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
             "attr": "Tiles © Esri", "overlay": True},
        ],
    },
    "esri_topo": {
        "nome": "Esri · Topográfico",
        "layers": [
            {"url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
             "attr": "Tiles © Esri", "overlay": False},
        ],
    },
    "esri_roads": {
        "nome": "Esri · Ruas",
        "layers": [
            {"url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
             "attr": "Tiles © Esri", "overlay": False},
        ],
    },

    # ---------------- Sentinel-2 cloudless ----------------
    "s2cloudless": {
        "nome": "Sentinel-2 cloudless (EOX)",
        "layers": [
            {"url": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg",
             "attr": "Sentinel-2 cloudless © EOX", "overlay": False},
        ],
    },

    # ---------------- OpenStreetMap ----------------
    "osm": {
        "nome": "OpenStreetMap · Padrão",
        "layers": [
            {"url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
             "attr": "© OpenStreetMap", "overlay": False},
        ],
    },
    "osm_hot": {
        "nome": "OpenStreetMap · Humanitário",
        "layers": [
            {"url": "https://tile-{s}.openstreetmap.fr/hot/{z}/{x}/{y}.png",
             "attr": "© OpenStreetMap HOT", "overlay": False},
        ],
    },

    # ---------------- CARTO ----------------
    "carto_light": {
        "nome": "CARTO · Claro",
        "layers": [
            {"url": "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png",
             "attr": "© OpenStreetMap © CARTO", "overlay": False},
        ],
    },
    "carto_dark": {
        "nome": "CARTO · Escuro",
        "layers": [
            {"url": "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
             "attr": "© OpenStreetMap © CARTO", "overlay": False},
        ],
    },

    # ---------------- Sem mapa ----------------
    "nenhum": {
        "nome": "Sem mapa (só polígono)",
        "layers": [],
    },
}

# Estilo padrão — híbrido é o mais útil para produtor se orientar
PROVIDER_DEFAULT = "google_hybrid"

st.set_page_config(page_title="IrrigaCerta", page_icon="💧", layout="wide")

storage.init_db()
demo_data.ensure_demo_talhoes()

# Estado da sessão: provider escolhido no sidebar
if "tile_provider" not in st.session_state:
    st.session_state["tile_provider"] = PROVIDER_DEFAULT

# Nomes dos meses em português — independentes do locale do sistema
MESES_PT = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
    7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez",
}


# ---------- helpers ----------
def _fmt_data(d) -> str:
    """Formata uma data como '21/out' em português."""
    return f"{d.day:02d}/{MESES_PT[d.month]}"


def _ticks(df, labels, max_ticks=8):
    """Gera tickvals/ticktext espaçados para o eixo X."""
    n = len(df)
    if n <= max_ticks:
        return list(range(n)), labels
    step = max(1, n // max_ticks)
    vals = list(range(0, n, step))
    return vals, [labels[i] for i in vals]


def _criar_mapa_folium(lat, lon, zoom, provider_key):
    """Cria um folium.Map com as camadas do provider escolhido. None se 'nenhum'."""
    provider = TILE_PROVIDERS.get(provider_key, TILE_PROVIDERS[PROVIDER_DEFAULT])
    if not provider["layers"]:
        return None

    m = folium.Map(location=[lat, lon], zoom_start=zoom, control_scale=True)
    for layer in provider["layers"]:
        folium.TileLayer(
            tiles=layer["url"],
            attr=layer["attr"],
            overlay=layer.get("overlay", False),
            control=False,
            name=layer.get("name", ""),
        ).add_to(m)
    return m


def _render_poligono_plotly(geom, lat, lon, altura=450, key_suffix=""):
    """Desenha o polígono puro com Plotly (sem tiles). Sempre funciona."""
    from shapely.geometry import shape

    poly = shape(geom)
    coords = list(poly.exterior.coords)
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=lons, y=lats,
        mode="lines",
        fill="toself",
        fillcolor="rgba(0,191,255,0.25)",
        line=dict(color="#00bfff", width=3),
        name="Talhão",
        hovertemplate="lon: %{x:.5f}<br>lat: %{y:.5f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[lon], y=[lat], mode="markers",
        marker=dict(size=12, color="#ff4444", symbol="x"),
        name="Centro",
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=altura,
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(title="Longitude", scaleanchor="y", scaleratio=1),
        yaxis=dict(title="Latitude"),
        template="plotly_white",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True,
                    key=f"plotly_poligono_{key_suffix}")


def _grafico_balanco_plotly(balanco: list):
    """Gráfico responsivo do nível de água no solo (Plotly)."""
    df = pd.DataFrame(balanco).sort_values("data").reset_index(drop=True)
    df["data"] = pd.to_datetime(df["data"])

    taw = float(df["taw"].iloc[0])
    raw = float(df["raw"].iloc[0])

    labels = [_fmt_data(d) for d in df["data"]]
    xs = list(range(len(df)))
    ys = df["dr"].tolist()

    fig = go.Figure()

    fig.add_shape(type="rect", x0=-0.5, x1=len(df) - 0.5,
                  y0=0, y1=raw,
                  fillcolor="#2ca02c", opacity=0.15,
                  line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-0.5, x1=len(df) - 0.5,
                  y0=raw, y1=taw,
                  fillcolor="#d62728", opacity=0.15,
                  line_width=0, layer="below")

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines+markers",
        name="Água consumida",
        line=dict(color="#1f77b4", width=2.5),
        marker=dict(size=6),
        text=labels,
        hovertemplate="<b>%{text}</b><br>Consumido: %{y:.1f} mm<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[xs[0], xs[-1]], y=[raw, raw], mode="lines",
        name=f"Limite de alerta ({raw:.0f} mm)",
        line=dict(color="#d62728", width=1.5, dash="dash"),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[xs[0], xs[-1]], y=[taw, taw], mode="lines",
        name=f"Capacidade do solo ({taw:.0f} mm)",
        line=dict(color="gray", width=1.5, dash="dot"),
        hoverinfo="skip",
    ))

    fig.add_annotation(x=len(df) - 1, y=raw / 2 if raw > 0 else 1,
                       text="Zona segura", showarrow=False,
                       font=dict(color="#2ca02c", size=11),
                       bgcolor="rgba(255,255,255,0.85)")
    fig.add_annotation(x=len(df) - 1, y=(raw + taw) / 2,
                       text="Zona de alerta", showarrow=False,
                       font=dict(color="#d62728", size=11),
                       bgcolor="rgba(255,255,255,0.85)")

    tickvals, ticktext = _ticks(df, labels)

    fig.update_layout(
        title=dict(text="Água consumida pelas plantas ao longo do tempo",
                   x=0.02, xanchor="left", font=dict(size=14)),
        xaxis=dict(tickvals=tickvals, ticktext=ticktext,
                   title="Data", tickangle=-45),
        yaxis=dict(title="Quantidade de água (mm)", rangemode="tozero"),
        height=420,
        margin=dict(l=70, r=30, t=80, b=80),
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
    )
    return fig


def _grafico_ndmi_plotly(sat_cache: list):
    """Gráfico responsivo da umidade da vegetação (Plotly)."""
    df = pd.DataFrame(sat_cache).sort_values("data").reset_index(drop=True)
    df["data"] = pd.to_datetime(df["data"])

    labels = [_fmt_data(d) for d in df["data"]]
    xs = list(range(len(df)))
    ys = df["ndmi"].tolist()

    fig = go.Figure()

    fig.add_shape(type="rect", x0=-0.5, x1=len(df) - 0.5,
                  y0=-0.2, y1=0.1,
                  fillcolor="#d62728", opacity=0.15,
                  line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-0.5, x1=len(df) - 0.5,
                  y0=0.1, y1=0.3,
                  fillcolor="#ffbf00", opacity=0.15,
                  line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-0.5, x1=len(df) - 0.5,
                  y0=0.3, y1=1.0,
                  fillcolor="#2ca02c", opacity=0.15,
                  line_width=0, layer="below")

    fig.add_annotation(x=len(df) - 1, y=-0.05, text="Seca",
                       showarrow=False,
                       font=dict(color="#d62728", size=11),
                       bgcolor="rgba(255,255,255,0.85)")
    fig.add_annotation(x=len(df) - 1, y=0.2, text="Moderada",
                       showarrow=False,
                       font=dict(color="#c68a00", size=11),
                       bgcolor="rgba(255,255,255,0.85)")
    fig.add_annotation(x=len(df) - 1, y=0.65, text="Úmida",
                       showarrow=False,
                       font=dict(color="#2ca02c", size=11),
                       bgcolor="rgba(255,255,255,0.85)")

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines+markers",
        name="Umidade das plantas",
        line=dict(color="#0a7a3f", width=2.5),
        marker=dict(size=10),
        customdata=labels,
        hovertemplate="<b>%{customdata}</b><br>NDMI: %{y:.2f}<extra></extra>",
    ))

    for i, v in enumerate(ys):
        fig.add_annotation(x=i, y=v, text=f"{v:.2f}",
                           showarrow=False, yshift=14,
                           font=dict(size=9, color="#0a7a3f"))

    tickvals, ticktext = _ticks(df, labels)

    fig.update_layout(
        title=dict(text="Umidade das plantas vista do satélite",
                   x=0.02, xanchor="left", font=dict(size=14)),
        xaxis=dict(tickvals=tickvals, ticktext=ticktext,
                   title="Data", tickangle=-45),
        yaxis=dict(title="Umidade da vegetação (0 a 1)", range=[-0.2, 1.0]),
        height=420,
        margin=dict(l=70, r=30, t=80, b=80),
        hovermode="closest",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
    )
    return fig


def _render_recomendacao(rec: dict):
    """Exibe a recomendação com cor adequada e explicação em linguagem leiga."""
    cor = rec.get("cor", "info")
    fn = {
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
        "info": st.info,
    }.get(cor, st.info)

    fn(f"**{rec['titulo']}**\n\n{rec['mensagem']}")
    if rec.get("explicacao"):
        st.caption(f"ℹ️ **Por quê?** {rec['explicacao']}")


def render_mapa_talhao(geom, lat, lon, talhao_id: str, altura=450):
    """Mapa do talhão com o estilo escolhido. Fallback Plotly se 'nenhum'."""
    provider_key = st.session_state.get("tile_provider", PROVIDER_DEFAULT)
    provider = TILE_PROVIDERS.get(provider_key, TILE_PROVIDERS[PROVIDER_DEFAULT])

    if not provider["layers"]:
        _render_poligono_plotly(geom, lat, lon, altura=altura,
                                key_suffix=talhao_id)
        st.caption(
            "⚠️ Fundo de mapa desativado. Escolha um estilo em "
            "**🗺️ Mapa de fundo** na barra lateral."
        )
        return

    m = _criar_mapa_folium(lat, lon, zoom=13, provider_key=provider_key)
    folium.GeoJson(
        geom,
        style_function=lambda _: {
            "color": "#00bfff", "weight": 3,
            "fillColor": "#00bfff", "fillOpacity": 0.15,
        },
    ).add_to(m)
    # Key muda com provider para forçar re-render quando troca o estilo
    st_folium(
        m, height=altura, use_container_width=True,
        key=f"map_talhao_{talhao_id}_{provider_key}",
    )


def _atualizar_clima(talhao: dict):
    """Fetch explícito de clima — chamado só por botão."""
    if config.DEMO_MODE:
        st.error("Modo demo LIGADO. Use `IRRIGACERTA_DEMO_MODE=0`.")
        return
    with st.spinner("Buscando NASA POWER + Open-Meteo..."):
        _h, _p, _err = climate.get_clima(
            talhao["id"], talhao["lat"], talhao["lon"],
            date.fromisoformat(talhao["data_plantio"]), force=True,
        )
    if _h:
        st.success(f"Clima atualizado: {len(_h)} dias + {len(_p)} previstos.")
        st.rerun()
    else:
        st.error(f"Falha: {_err}")


def _atualizar_satelite(talhao: dict):
    """Roda em subprocesso para isolar eventuais segfaults de rasterio/GDAL."""
    if config.DEMO_MODE:
        st.error("Modo demo LIGADO. Use `IRRIGACERTA_DEMO_MODE=0`.")
        return
    if not _tem_satelite():
        st.error("Instale `rasterio` e `numpy` (já no requirements).")
        return

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    dias = getattr(config, "DIAS_SATELITE_DEFAULT", 60)

    with st.spinner("Buscando Sentinel-2 em subprocesso (1–5 min)..."):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "scripts.fetch_satelite",
                 talhao["id"], str(dias)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            st.error("Timeout (>10 min). Reduza `MAX_CENAS_PROCESSAR` em `config.py`.")
            return

    with st.expander("Log do subprocesso (stdout / stderr)"):
        st.markdown("**stdout:**")
        st.code((proc.stdout or "").strip() or "(vazio)")
        st.markdown("**stderr:**")
        st.code((proc.stderr or "").strip() or "(vazio)")

    if proc.returncode == 0:
        st.success("Satélite atualizado.")
        st.rerun()
    else:
        msg = EXIT_CODES.get(proc.returncode, f"erro desconhecido ({proc.returncode})")
        st.error(f"Subprocesso falhou — {msg}. Veja o log acima.")


# ---------- página: cadastro ----------
def render_cadastro():
    st.header("Cadastro de talhão")
    st.caption(
        "Desenhe o polígono do talhão no mapa "
        "(duplo clique fecha o polígono)."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        provider_key = st.session_state.get("tile_provider", PROVIDER_DEFAULT)
        provider = TILE_PROVIDERS.get(provider_key, TILE_PROVIDERS[PROVIDER_DEFAULT])

        # No cadastro, se 'nenhum', usa OSM só para permitir desenho
        if not provider["layers"]:
            m = _criar_mapa_folium(
                config.DEFAULT_CENTER[0], config.DEFAULT_CENTER[1],
                zoom=12, provider_key="osm",
            )
            st.caption(
                "⚠️ 'Sem mapa' não permite desenhar. Usando OpenStreetMap apenas "
                "para o cadastro."
            )
        else:
            m = _criar_mapa_folium(
                config.DEFAULT_CENTER[0], config.DEFAULT_CENTER[1],
                zoom=12, provider_key=provider_key,
            )

        Draw(
            export=False,
            draw_options={
                "polyline": False, "polygon": True, "rectangle": True,
                "circle": False, "marker": False, "circlemarker": False,
            },
        ).add_to(m)
        desenho = st_folium(m, height=450, use_container_width=True,
                            key=f"map_cadastro_{provider_key}")

    with col2:
        nome = st.text_input("Nome do talhão", value="Talhão teste")
        cultura = st.selectbox("Cultura", list(config.KC.keys()))

        data_plantio = st.date_input(
            "Data de plantio",
            value=date.today() - timedelta(days=60),
            help="NASA POWER tem latência de ~7 dias. Use datas de plantio com ≥ 8 dias.",
        )
        if (date.today() - data_plantio).days < 8:
            st.warning(
                "Data muito recente. NASA POWER só tem dados até hoje−7; "
                "o balanço hídrico ficará sem histórico. Use uma data mais antiga."
            )

        textura = st.selectbox("Textura do solo", list(config.TAW_POR_METRO.keys()))
        sistema = st.selectbox("Sistema de irrigação",
                               ["gotejamento", "aspersao", "pivo", "sulco"])
        vazao = st.number_input("Vazão do sistema (mm/h)", min_value=0.1,
                                value=5.0, step=0.1)

    geom = None
    if desenho and desenho.get("all_drawings"):
        geom = desenho["all_drawings"][0]["geometry"]
        try:
            info = geo.validar_geometria(geom)
            st.success(f"Polígono válido — {info['area_ha']:.2f} ha")
            if info["area_ha"] > 500:
                st.warning(
                    f"Talhão de {info['area_ha']:.0f} ha é grande para NDMI por talhão. "
                    "Para uma demo realista, desenhe ≤ 500 ha (use zoom alto no mapa)."
                )
            geom = info
        except ValueError as e:
            st.error(str(e))
            geom = None
    else:
        st.info("Aguardando desenho do talhão no mapa.")

    if st.button("Salvar talhão", type="primary", disabled=geom is None):
        tid = storage.criar_talhao(
            nome=nome, geometry=geom["geometry"], area_ha=geom["area_ha"],
            cultura=cultura, data_plantio=data_plantio.isoformat(),
            textura_solo=textura, sistema_irrigacao=sistema,
            vazao_mm_h=float(vazao), lat=geom["lat"], lon=geom["lon"],
        )
        st.success(f"Talhão salvo com id `{tid}`. Vá para o Dashboard.")


# ---------- página: dashboard (SÓ LÊ CACHE — nunca busca) ----------
def render_dashboard():
    # st.header("Dashboard — recomendação de irrigação")

    talhoes = storage.listar_talhoes()
    if not talhoes:
        st.warning("Nenhum talhão cadastrado. Vá em **Cadastro** primeiro.")
        return

    opcoes = {f"{t['nome']} ({t['id']})": t["id"] for t in talhoes}
    rotulo = st.selectbox("Talhão", list(opcoes.keys()))
    talhao = storage.obter_talhao(opcoes[rotulo])

    clim_cache = storage.ler_cache("clima", talhao["id"])
    hist = clim_cache["historico"] if clim_cache else {}
    prev = clim_cache["previsao"] if clim_cache else {}
    sat_cache = storage.ler_cache("sat", talhao["id"]) or []

    if not hist:
        st.warning(
            "Sem dados de clima em cache para este talhão. "
            "Clique em **Carregar clima** abaixo."
        )
        if st.button("🌦️ Carregar clima (NASA POWER + Open-Meteo)", type="primary"):
            _atualizar_clima(talhao)

    balanco, taw, raw = agronomy.balanco_hidrico(
        hist, talhao["cultura"],
        date.fromisoformat(talhao["data_plantio"]),
        talhao["textura_solo"], talhao["lat"],
    )
    rec = recommender.recomendar(balanco, prev, talhao["vazao_mm_h"])

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("📍 Talhão")
        render_mapa_talhao(talhao["geometry"], talhao["lat"], talhao["lon"],
                           talhao["id"])
    with c2:
        st.subheader("🚿 Recomendação de hoje")
        _render_recomendacao(rec)

        if balanco:
            st.divider()
            dr = balanco[-1]["dr"]
            pct = (dr / taw) * 100 if taw > 0 else 0
            st.markdown("#### 💧 Nível de água no solo")
            st.progress(
                min(pct / 100, 1.0),
                text=f"**{pct:.0f}%** consumido — {dr:.0f} mm de {taw:.0f} mm",
            )

            with st.expander("❓ O que significam estes números?"):
                st.markdown(f"""
- **Água já consumida pelas plantas ({dr:.0f} mm):** quanto de água as plantas já usaram desde a última chuva ou irrigação. Quanto maior, mais seco o solo está.
- **Capacidade do solo ({taw:.0f} mm):** o total de água que o solo guarda depois de uma chuva forte. Varia com o tipo de solo (arenoso guarda menos que argiloso).
- **Limite de alerta ({raw:.0f} mm):** quando a água consumida passa desse valor, as plantas começam a sofrer com falta de água. É a hora de regar.

📏 **1 mm de água = 1 litro por metro quadrado.** Para um talhão de 1 hectare (10.000 m²), 1 mm equivale a 10.000 litros de água.

📊 **Fontes:** clima diário do satélite **NASA POWER**; método de balanço hídrico segundo **FAO-56** (padrão da ONU para agricultura).
                """)

        st.divider()
        st.caption(
            f"**Cultura:** {talhao['cultura']} · "
            f"**Solo:** {talhao['textura_solo']} · "
            f"**Irrigação:** {talhao['sistema_irrigacao']} ({talhao['vazao_mm_h']} mm/h)"
        )

    # ---- gráficos (um abaixo do outro, responsivos) ----
    st.divider()

    st.subheader("💧 Água no solo (últimos 60 dias)")
    if balanco:
        fig = _grafico_balanco_plotly(balanco)
        st.plotly_chart(fig, use_container_width=True, key="graf_balanco")
        st.caption(
            "🟢 **Zona segura:** as plantas têm água suficiente.  "
            "🔴 **Zona de alerta:** as plantas precisam de água.  "
            "A linha azul mostra quanto as plantas já consumiram."
        )
    else:
        st.info("Aguardando dados de clima.")

    st.divider()

    st.subheader("🛰️ Umidade das plantas (satélite)")
    if sat_cache:
        fig = _grafico_ndmi_plotly(sat_cache)
        st.plotly_chart(fig, use_container_width=True, key="graf_ndmi")

        ultimo = sat_cache[-1]["ndmi"]
        if ultimo >= 0.3:
            estado = "🟢 **Vegetação úmida** — as plantas estão com boa quantidade de água."
        elif ultimo >= 0.1:
            estado = "🟡 **Umidade moderada** — fique atento, pode ser hora de regar em breve."
        else:
            estado = "🔴 **Vegetação seca** — as plantas estão com falta de água."

        st.caption(f"**Última medição:** {ultimo:.2f} → {estado}")

        with st.expander("❓ O que é NDMI e como ler este gráfico?"):
            st.markdown("""
O **NDMI** (Índice de Umidade por Diferença Normalizada) mede a quantidade de água nas folhas das plantas, vista do espaço.

**Escala de 0 a 1:**
- 🟢 Acima de **0,30**: vegetação bem hidratada
- 🟡 Entre **0,10 e 0,30**: umidade moderada
- 🔴 Abaixo de **0,10**: vegetação seca, precisa de água

**Como usar:** se o NDMI cai ao longo das medições, as plantas estão perdendo água. Se sobe, estão recuperando (após chuva ou irrigação).

📡 **Fonte:** satélite **Sentinel-2** (União Europeia / programa Copernicus), resolução de 20 metros, atualizado a cada 5 dias, gratuito.

**Fórmula:** NDMI = (NIR − SWIR) / (NIR + SWIR), usando as bandas infravermelho próximo (B08) e infravermelho de ondas curtas (B11).
            """)
    else:
        cache_file = storage.cache_path("sat", talhao["id"])
        if cache_file.exists():
            st.warning(
                "Cache existe mas está vazio — a última busca não encontrou "
                "cena válida. Tente de novo ou aumente `MAX_NUVEM_DEFAULT` / "
                "`MAX_CENAS_PROCESSAR` em `config.py`."
            )
        else:
            st.info("Ainda não há busca de satélite para este talhão.")
        if st.button("🛰️ Buscar satélite (Sentinel-2)"):
            _atualizar_satelite(talhao)

    # ---- gerenciar ----
    st.divider()
    with st.expander("⚙️ Gerenciar este talhão"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("🗑️ Excluir talhão", type="secondary"):
                if storage.deletar_talhao(talhao["id"]):
                    st.success(f"Talhão `{talhao['id']}` excluído.")
                    st.rerun()
                else:
                    st.error("Não foi possível excluir.")
        with col_b:
            if st.button("🌦️ Re-buscar clima"):
                _atualizar_clima(talhao)
        with col_c:
            if st.button("🛰️ Re-buscar satélite"):
                _atualizar_satelite(talhao)


# ---------- página: sobre ----------
def render_sobre():
    st.header("Sobre o IrrigaCerta")
    st.markdown(
        """
**Problema.** O produtor irriga "no feeling"; desperdiça água e energia ou perde safra por atraso.

**Solução.** Assistente que combina **satélite Sentinel-2** (NDVI/NDMI), **clima** (NASA POWER + Open-Meteo)
e **agronomia** (balanço hídrico FAO-56, Kc por cultura) para dizer **quando e quanto irrigar**.

**Diferencial.** Sem sensor; dados abertos; recomendação explicável.

**Próximo passo.** POC com cooperativa (5 propriedades / 60 dias), integrada ao Hub Semear/FAEB/SENAR.
        """
    )


# ---------- navegação + seletor de mapa ----------
st.sidebar.title("💧 IrrigaCerta")
st.sidebar.caption("Resiliência hídrica no agro")
pagina = st.sidebar.radio("Navegar", ["Dashboard", "Cadastro", "Sobre"])

st.sidebar.divider()
st.sidebar.subheader("🗺️ Mapa de fundo")
provider_keys = list(TILE_PROVIDERS.keys())
idx_atual = provider_keys.index(
    st.session_state.get("tile_provider", PROVIDER_DEFAULT)
) if st.session_state.get("tile_provider") in provider_keys else 0

st.session_state["tile_provider"] = st.sidebar.selectbox(
    "Estilo",
    provider_keys,
    index=idx_atual,
    format_func=lambda k: TILE_PROVIDERS[k]["nome"],
    label_visibility="collapsed",
    key="select_provider",
)

if not TILE_PROVIDERS[st.session_state["tile_provider"]]["layers"]:
    st.sidebar.info("Sem tiles — apenas o polígono será desenhado.")
else:
    st.sidebar.caption(
        "Se o mapa não carregar, troque o estilo acima. "
        "O Google e o Esri · Satélite são os mais confiáveis no Brasil."
    )

st.sidebar.divider()
st.sidebar.caption(f"Modo demo: {'ON' if config.DEMO_MODE else 'OFF'}")
st.sidebar.caption(f"Cache: `{config.CACHE_DIR}`")

if pagina == "Dashboard":
    render_dashboard()
elif pagina == "Cadastro":
    render_cadastro()
else:
    render_sobre()

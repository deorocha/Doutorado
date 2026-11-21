"""
Monitor de Lâminas Histológicas — versão simplificada, com limiares por slot.
"""
import re
import time
import threading

import pandas as pd
import streamlit as st

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    st.error("Instale pyserial:  pip install pyserial")
    st.stop()

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st.error("Instale streamlit-autorefresh:  pip install streamlit-autorefresh")
    st.stop()

st.set_page_config(page_title="Monitor de Lâminas", page_icon="🔬", layout="wide")


# =========================================================
#  Estado global (sobrevive a reruns via cache_resource)
# =========================================================
class Estado:
    def __init__(self):
        self.lock = threading.Lock()
        self.leituras = [None] * 16
        self.bytes = 0
        self.ciclos = 0
        self.ultima_linha = ""
        self.erro = None
        self.rodando = False
        self.stop_event = None
        self.thread = None
        # ---- estatísticas por slot (min/max observados) ----
        self.slot_min = [None] * 16
        self.slot_max = [None] * 16
        # ---- limiares individuais + flag ----
        self.limiares_slot = [None] * 16
        self.usar_individual = False


@st.cache_resource
def _get_estado(v: int = 2):      # bump `v` sempre que mudar a classe Estado
    return Estado()


E = _get_estado()
REGEX = re.compile(r"Canal\s+(\d+)\s*:\s*(\d+)")


# =========================================================
#  Thread de leitura
# =========================================================
def _loop(porta, baud, stop, E):
    ser = None
    ultimo_erro = None
    for tentativa in range(1, 6):
        if stop.is_set():
            with E.lock:
                E.rodando = False
            return
        try:
            ser = serial.Serial(porta, baud, timeout=1)
            break
        except Exception as e:
            ultimo_erro = e
            time.sleep(0.6)

    if ser is None:
        with E.lock:
            E.erro = (
                f"❌ Não foi possível abrir **{porta}** após 5 tentativas.\n\n"
                f"**Último erro:** `{ultimo_erro}`\n\n"
                "**Verifique, nesta ordem:**\n"
                "1. O **Monitor Serial da IDE do Arduino** está fechado? "
                "(Ferramentas → Monitor Serial → fechar)\n"
                "2. Há **outra aba do navegador** com este app aberto? "
                "(feche todas)\n"
                "3. Há **outro `streamlit run`** rodando em outro terminal? "
                "(feche com Ctrl+C)\n"
                "4. **Desconecte e reconecte** o cabo USB do Arduino "
                "(reseta o driver CH340)\n"
                "5. Se nada resolver, reinicie o PC."
            )
            E.rodando = False
        return

    time.sleep(2)  # aguarda auto-reset do Nano
    buf = [None] * 16

    while not stop.is_set():
        try:
            linha = ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception as e:
            with E.lock:
                E.erro = f"Erro de leitura: {e}"
            break

        if not linha:
            continue

        with E.lock:
            E.bytes += len(linha) + 1
            E.ultima_linha = linha

        m = REGEX.search(linha)
        if m:
            ch, val = int(m.group(1)), int(m.group(2))
            if 0 <= ch < 16:
                buf[ch] = val
            continue

        if linha.startswith("---"):
            with E.lock:
                E.leituras = buf.copy()
                E.ciclos += 1
                # ---- atualiza estatísticas por slot ----
                for i in range(16):
                    v = buf[i]
                    if v is None:
                        continue
                    if E.slot_min[i] is None or v < E.slot_min[i]:
                        E.slot_min[i] = v
                    if E.slot_max[i] is None or v > E.slot_max[i]:
                        E.slot_max[i] = v
            buf = [None] * 16

    try:
        ser.close()
    except Exception:
        pass
    with E.lock:
        E.rodando = False


def iniciar(porta, baud):
    with E.lock:
        if E.rodando:
            return
        E.stop_event = threading.Event()
        E.rodando = True
        E.bytes = 0
        E.ciclos = 0
        E.erro = None
        E.leituras = [None] * 16
        E.slot_min = [None] * 16
        E.slot_max = [None] * 16

    E.thread = threading.Thread(
        target=_loop, args=(porta, baud, E.stop_event, E), daemon=True
    )
    E.thread.start()


def parar():
    with E.lock:
        if E.stop_event:
            E.stop_event.set()
    if E.thread and E.thread.is_alive():
        E.thread.join(timeout=3.0)


# =========================================================
#  Sidebar
# =========================================================
with st.sidebar:
    st.header("⚙️ Conexão")

    portas = [p.device for p in serial.tools.list_ports.comports()]
    if portas:
        porta = st.selectbox("Porta serial", portas)
    else:
        porta = st.text_input("Porta serial", value="/dev/ttyUSB0")

    baud = st.selectbox("Baud rate", [115200, 9600, 57600], index=0)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶ Iniciar", use_container_width=True, disabled=E.rodando):
            iniciar(porta, baud)
    with c2:
        if st.button("⏹ Parar", use_container_width=True, disabled=not E.rodando):
            parar()

    if E.rodando:
        st.success("● Lendo da serial")
    else:
        st.info("○ Parado")

    st.divider()
    st.header("🎯 Detecção")

    # ---------- Auto-sugestão do limiar global ----------
    with E.lock:
        valores = [v for v in E.leituras if v is not None]

    if valores and min(valores) != max(valores):
        vmin, vmax = min(valores), max(valores)
        # OBS: /1.10 gera limiar ABAIXO de vmin. Se a classificação parecer
        # invertida, troque para `* 1.10` (ou `int(vmax / 1.10)` no modo Menor).
        sugestao = int(vmin / 1.10)
        st.caption(f"Faixa atual: **{vmin}** (min) … **{vmax}** (max)")
        st.caption(f"Limiar global sugerido: **{sugestao}**")
    elif valores:
        sugestao = 500
        st.warning(
            f"Todos os canais leem **{valores[0]}**. "
            "Verifique a fiação dos LDRs / do MUX."
        )
    else:
        sugestao = 500

    if "limiar" not in st.session_state:
        st.session_state.limiar = sugestao

    limiar = st.slider(
        "Limiar global (ADC 0–1023)", 0, 1023,
        key="limiar", step=10,
    )

    if valores and min(valores) != max(valores):
        def _aplicar_sugestao():
            st.session_state.limiar = sugestao

        st.button(
            f"Aplicar sugestão global ({sugestao})",
            on_click=_aplicar_sugestao,
            use_container_width=True,
        )

    modo = st.radio(
        "Lâmina presente quando a leitura for:",
        ["Maior que o limiar", "Menor que o limiar"],
        index=0,
        help=(
            "Dica: se **todos os slots vazios** aparecerem verdes, "
            "troque a direção. O modo (Maior/Menor) vale tanto para "
            "o limiar global quanto para os individuais."
        ),
    )

    # ---------- Limiares por slot ----------
    with st.expander("🔧 Limiares individuais por slot", expanded=False):
        st.caption(
            "Cada LDR tem resposta ligeiramente diferente. Aqui você pode "
            "definir um limiar específico por slot. **Vazio** = usa o global."
        )

        def _toggle_ind():
            E.usar_individual = st.session_state.usar_individual_widget

        st.checkbox(
            "Usar limiar individual (sobrepõe o global)",
            value=E.usar_individual,
            key="usar_individual_widget",
            on_change=_toggle_ind,
        )

        # Snapshot + sugestões
        with E.lock:
            s_min = list(E.slot_min)
            s_max = list(E.slot_max)
            s_lims = list(E.limiares_slot)

        sugeridos = []
        for i in range(16):
            if (s_min[i] is not None and s_max[i] is not None
                    and s_min[i] != s_max[i]):
                sugeridos.append(int(s_min[i] / 1.10))
            else:
                sugeridos.append(None)

        # Editor "versionado" para permitir reset limpo
        if "ed_ver" not in st.session_state:
            st.session_state.ed_ver = 0
        ver = st.session_state.ed_ver
        ed_key = f"ed_lim_{ver}"

        def _on_edit_limiares():
            edited = st.session_state.get(ed_key)
            if edited is None:
                return
            with E.lock:
                E.limiares_slot = [
                    None if pd.isna(x) else int(x) for x in edited["Limiar"]
                ]

        df_edit = pd.DataFrame({
            "Slot": [f"L{i+1}" for i in range(16)],
            "Limiar": pd.array(s_lims, dtype="Int64"),
        })

        st.data_editor(
            df_edit,
            column_config={
                "Slot": st.column_config.TextColumn(disabled=True),
                "Limiar": st.column_config.NumberColumn(
                    "Limiar", min_value=0, max_value=1023,
                    step=1, format="%d",
                    help="Vazio = usa o limiar global",
                ),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key=ed_key,
            on_change=_on_edit_limiares,
        )

        b1, b2 = st.columns(2)
        if b1.button("✨ Sugestões", use_container_width=True,
                     help="Preenche os 16 limiares com base em min/1.10 de cada slot"):
            with E.lock:
                E.limiares_slot = list(sugeridos)
            st.session_state.ed_ver += 1
            st.rerun()

        if b2.button("🧹 Limpar", use_container_width=True,
                     help="Volta todos os slots a usar o limiar global"):
            with E.lock:
                E.limiares_slot = [None] * 16
            st.session_state.ed_ver += 1
            st.rerun()

        if st.button("🗑️ Zerar estatísticas (min/máx)",
                     use_container_width=True,
                     help="Útil após trocar lâmpada, mexer na fiação etc."):
            with E.lock:
                E.slot_min = [None] * 16
                E.slot_max = [None] * 16
            st.rerun()

        with st.popover("📊 Estatísticas observadas", use_container_width=True):
            stats_df = pd.DataFrame({
                "Slot": [f"L{i+1}" for i in range(16)],
                "Mín": pd.array(s_min, dtype="Int64"),
                "Máx": pd.array(s_max, dtype="Int64"),
                "Sug": pd.array(sugeridos, dtype="Int64"),
            })
            st.dataframe(
                stats_df, hide_index=True,
                use_container_width=True, height=350,
            )
            
# =========================================================
#  Área principal
# =========================================================
st.title("🔬 Monitor de Lâminas Histológicas")

# Snapshot consistente
with E.lock:
    leituras = list(E.leituras)
    limiares_slot = list(E.limiares_slot)
    usar_ind = E.usar_individual
    bytes_ = E.bytes
    ciclos = E.ciclos
    ultima = E.ultima_linha
    erro = E.erro

if erro:
    st.error(erro)

if E.rodando and bytes_ == 0:
    st.warning(
        "A porta abriu, mas nenhum dado chegou. "
        "**Feche o Monitor Serial da IDE do Arduino** e reinicie."
    )

# ---- Classificação (por slot) ----
def limiar_de(i: int) -> int:
    if usar_ind and limiares_slot[i] is not None:
        return limiares_slot[i]
    return limiar


def esta_presente(i: int, v):
    if v is None:
        return None
    lim = limiar_de(i)
    if modo == "Maior que o limiar":
        return v > lim
    return v < lim


# ---- Grid 8×2 ----
presentes = ausentes = sem = 0
slots = []
op = ">" if modo == "Maior que o limiar" else "<"
for i in range(16):
    v = leituras[i]
    estado = esta_presente(i, v)
    lim_usado = limiar_de(i)

    if estado is None:
        cor, icone = "#7f8c8d", "·"
        sem += 1
    elif estado:
        cor, icone = "#27ae60", "✔"
        presentes += 1
    else:
        cor, icone = "#c0392b", "✖"
        ausentes += 1

    txt = "—" if v is None else str(v)
    slots.append(
        f'<div style="aspect-ratio:1/3;background:{cor};color:#fff;'
        f'border-radius:8px;padding:6px;display:flex;flex-direction:column;'
        f'align-items:center;justify-content:space-between;'
        f'font-family:sans-serif;box-sizing:border-box">'
        f'<div style="font-weight:700;font-size:14px">L{i+1}</div>'
        f'<div style="font-size:22px">{icone}</div>'
        f'<div style="font-size:10px;opacity:.9">{txt}</div>'
        f'<div style="font-size:9px;opacity:.75">{op}{lim_usado}</div>'
        f'</div>'
    )

grid = (
    '<div style="display:grid;grid-template-columns:repeat(8,1fr);'
    'gap:10px;max-width:800px;margin:10px auto">'
    + "".join(slots) +
    '</div>'
)
st.markdown(grid, unsafe_allow_html=True)

# ---- Métricas ----
st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("🟢 Presentes", f"{presentes}/16")
m2.metric("🔴 Ausentes", f"{ausentes}/16")
m3.metric("⚪ Sem leitura", f"{sem}/16")
m4.metric("📦 Ciclos", ciclos)

# ---- Diagnóstico enxuto ----
with st.expander("🩺 Diagnóstico", expanded=True):
    modo_lim = "individual" if usar_ind else "global"
    st.write(
        f"**Bytes recebidos:** {bytes_} | "
        f"**Ciclos completos:** {ciclos} | "
        f"**Modo de limiar:** {modo_lim} "
        f"(global = {limiar}) | "
        f"**Última linha:** `{ultima or '(vazio)'}`"
    )

    if any(v is not None for v in leituras):
        tabela = []
        for i in range(16):
            lim_i = limiar_de(i)
            tabela.append({
                "Slot": f"L{i+1}",
                "Valor": (leituras[i] if leituras[i] is not None else "—"),
                "Limiar": lim_i,
            })
        esquerda, direita = st.columns(2)
        with esquerda:
            st.table(tabela[:8])
        with direita:
            st.table(tabela[8:])

# ---- Auto-refresh enquanto estiver lendo ----
if E.rodando:
    st_autorefresh(interval=300, key="refresh")

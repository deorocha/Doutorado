"""
Monitor de Lâminas Histológicas — versão simplificada.
"""
import re
import time
import threading

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


@st.cache_resource
def _get_estado(v: int = 1):      # bump `v` sempre que mudar a classe Estado
    return Estado()


E = _get_estado()
REGEX = re.compile(r"Canal\s+(\d+)\s*:\s*(\d+)")


# =========================================================
#  Thread de leitura
# =========================================================
def _loop(porta, baud, stop, E):
    # ---- Tenta abrir com retry (a porta pode estar sendo liberada) ----
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

    # ---------- Auto-sugestão de limiar ----------
    with E.lock:
        valores = [v for v in E.leituras if v is not None]

    if valores and min(valores) != max(valores):
        vmin, vmax = min(valores), max(valores)
        sugestao = (vmin + vmax) // 2
        st.caption(f"Faixa atual: **{vmin}** (min) … **{vmax}** (max)")
        st.caption(f"Limiar sugerido: **{sugestao}**")
    elif valores:
        sugestao = 500
        st.warning(
            f"Todos os canais leem **{valores[0]}**. "
            "Verifique a fiação dos LDRs / do MUX."
        )
    else:
        sugestao = 500

    # ---------- Slider com estado persistente ----------
    if "limiar" not in st.session_state:
        st.session_state.limiar = sugestao

    limiar = st.slider(
        "Limiar (ADC 0–1023)", 0, 1023,
        key="limiar", step=10,
    )

    if valores and min(valores) != max(valores):
        if st.button(f"Aplicar sugestão ({sugestao})", use_container_width=True):
            st.session_state.limiar = sugestao
            st.rerun()

    modo = st.radio(
        "Lâmina presente quando a leitura for:",
        ["Maior que o limiar", "Menor que o limiar"],
        index=0,
        help=(
            "Dica: se **todos os slots vazios** aparecerem verdes, "
            "troque a direção. Se com 'Maior' todos ficarem vermelhos "
            "e com 'Menor' todos verdes (ou vice-versa), o limiar "
            "está fora da faixa real — use 'Aplicar sugestão'."
        ),
    )


# =========================================================
#  Área principal
# =========================================================
st.title("🔬 Monitor de Lâminas Histológicas")

# Snapshot consistente
with E.lock:
    leituras = list(E.leituras)
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


# ---- Classificação ----
def esta_presente(v):
    if v is None:
        return None
    if modo == "Maior que o limiar":
        return v > limiar
    return v < limiar


# ---- Grid 8×2 ----
presentes = ausentes = sem = 0
slots = []
for i in range(16):
    v = leituras[i]
    estado = esta_presente(v)

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
    st.write(
        f"**Bytes recebidos:** {bytes_} | "
        f"**Ciclos completos:** {ciclos} | "
        f"**Última linha:** `{ultima or '(vazio)'}`"
    )

    if any(v is not None for v in leituras):
        tabela = [
            {"Slot": f"L{i+1}", "Valor": (leituras[i] if leituras[i] is not None else "—")}
            for i in range(16)
        ]
        # Duas colunas de 8 slots cada
        esquerda, direita = st.columns(2)
        with esquerda:
            st.table(tabela[:8])
        with direita:
            st.table(tabela[8:])


# ---- Auto-refresh enquanto estiver lendo ----
if E.rodando:
    st_autorefresh(interval=300, key="refresh")

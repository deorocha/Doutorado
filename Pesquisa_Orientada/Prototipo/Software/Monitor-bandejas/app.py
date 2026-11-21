"""
Monitor de Bandejas — sensores Hall 3144 + PCF8574 via serial.
Layout físico: 1 coluna × 8 linhas.
Bandeja: 184 × 8 mm  |  espaçamento entre bandejas: 10 mm.
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

st.set_page_config(page_title="Monitor de Bandejas", page_icon="🧪", layout="wide")

NUM_SLOTS = 8


# =========================================================
#  Estado global (sobrevive a reruns via cache_resource)
# =========================================================
class Estado:
    def __init__(self):
        self.lock = threading.Lock()
        self.leituras = [None] * NUM_SLOTS
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
                "1. O **Monitor Serial da IDE do Arduino** está fechado?\n"
                "2. Há **outra aba do navegador** com este app aberto?\n"
                "3. Há **outro `streamlit run`** rodando em outro terminal?\n"
                "4. **Desconecte e reconecte** o cabo USB do Arduino.\n"
                "5. Se nada resolver, reinicie o PC."
            )
            E.rodando = False
        return

    time.sleep(2)          # aguarda auto-reset do Nano
    buf = [None] * NUM_SLOTS

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
            if 0 <= ch < NUM_SLOTS:
                buf[ch] = val
            continue

        if linha.startswith("---"):
            with E.lock:
                E.leituras = buf.copy()
                E.ciclos += 1
            buf = [None] * NUM_SLOTS

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
        E.leituras = [None] * NUM_SLOTS

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
    st.header("📐 Geometria")
    st.caption(
        "**Bandeja:** 184 × 8 mm  \n"
        "**Espaçamento:** 10 mm  \n"
        "**Layout:** 1 coluna × 8 linhas"
    )

    st.divider()
    st.header("🔎 Legenda")
    st.markdown(
        "<span style='color:#27ae60;font-size:20px'>●</span> "
        "Ímã detectado — bandeja **presente**  \n"
        "<span style='color:#c0392b;font-size:20px'>●</span> "
        "Sem ímã — bandeja **ausente**  \n"
        "<span style='color:#7f8c8d;font-size:20px'>●</span> "
        "Sem leitura",
        unsafe_allow_html=True,
    )


# =========================================================
#  Área principal
# =========================================================
st.title("🧪 Monitor de Bandejas")
st.caption(
    "Representação em escala do rack: cada barra é uma bandeja de **184 × 8 mm**, "
    "separadas por **10 mm**."
)

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


# =========================================================
#  Painel gráfico — 1 coluna × 8 linhas, em escala
# =========================================================
# Proporções físicas:
#   bandeja 184 mm x 8 mm   ->  slot muito largo e fino
#   gap entre bandejas 10 mm
# Escala escolhida: 4 px/mm  ->  banda = 736 px x 32 px ; gap = 40 px
SLOT_W = 736      # 184 mm * 4
SLOT_H = 32       # 8 mm * 4
GAP_H  = 30       # 10 mm * 4


def _slot_html(i, valor):
    """Renderiza uma bandeja (barra horizontal) conforme o estado do sensor."""
    if valor is None:
        cor, icone, texto, raw = "#7f8c8d", "·", "Sem leitura", "—"
    elif valor == 0:                      # ímã detectado = bandeja presente
        cor, icone, texto, raw = "#27ae60", "✔", "Bandeja presente", "0"
    else:                                  # sem ímã = bandeja ausente
        cor, icone, texto, raw = "#c0392b", "✖", "Bandeja ausente", "1"

    return (
        f'<div style="'
        f'width:{SLOT_W}px;height:{SLOT_H}px;background:{cor};color:#fff;'
        f'border-radius:5px;display:flex;align-items:center;'
        f'padding:0 14px;box-sizing:border-box;'
        f'font-family:sans-serif;font-size:13px;'
        f'box-shadow:inset 0 0 0 1px rgba(0,0,0,0.18), 0 1px 3px rgba(0,0,0,0.22);'
        f'">'
        # Etiqueta do slot (esquerda)
        f'<span style="font-weight:700;letter-spacing:.5px;min-width:34px;">'
        f'L{i+1}</span>'
        # Texto central
        f'<span style="flex:1;text-align:center;font-size:13px;">'
        f'{icone}&nbsp; {texto}</span>'
        # Valor bruto (direita)
        f'<span style="opacity:.85;font-size:11px;font-family:monospace;">'
        f'{raw}</span>'
        f'</div>'
    )


slots_html = "".join(_slot_html(i, leituras[i]) for i in range(NUM_SLOTS))

# Container central com aparência de "rack"
painel = (
    f'<div style="'
    f'display:flex;justify-content:center;margin:24px 0;'
    f'">'
    f'  <div style="'
    f'background:#eef1f4;border-radius:12px;padding:24px;'
    f'box-shadow:0 3px 10px rgba(0,0,0,0.08);'
    f'">'
    f'    <div style="'
    f'display:flex;flex-direction:column;gap:{GAP_H}px;'
    f'">'
    f'{slots_html}'
    f'    </div>'
    f'  </div>'
    f'</div>'
)

st.markdown(painel, unsafe_allow_html=True)


# =========================================================
#  Métricas
# =========================================================
st.divider()
presentes = sum(1 for v in leituras if v == 0)
ausentes  = sum(1 for v in leituras if v == 1)
sem       = sum(1 for v in leituras if v is None)

m1, m2, m3, m4 = st.columns(4)
m1.metric("🟢 Bandejas presentes", f"{presentes}/{NUM_SLOTS}")
m2.metric("🔴 Bandejas ausentes",  f"{ausentes}/{NUM_SLOTS}")
m3.metric("⚪ Sem leitura",        f"{sem}/{NUM_SLOTS}")
m4.metric("📦 Ciclos",             ciclos)


# =========================================================
#  Diagnóstico
# =========================================================
with st.expander("🩺 Diagnóstico", expanded=True):
    st.write(
        f"**Bytes recebidos:** {bytes_} | "
        f"**Ciclos completos:** {ciclos} | "
        f"**Última linha:** `{ultima or '(vazio)'}`"
    )

    if any(v is not None for v in leituras):
        st.table(
            [
                {
                    "Slot": f"L{i+1}",
                    "Sensor Hall": f"H{i+1}",
                    "Valor bruto": leituras[i] if leituras[i] is not None else "—",
                    "Estado": (
                        "—" if leituras[i] is None
                        else ("Presente" if leituras[i] == 0 else "Ausente")
                    ),
                }
                for i in range(NUM_SLOTS)
            ]
        )


# =========================================================
#  Auto-refresh enquanto estiver lendo
# =========================================================
if E.rodando:
    st_autorefresh(interval=300, key="refresh")

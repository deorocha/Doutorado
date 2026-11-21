import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import time
import math
import random
from itertools import permutations
import io
from PIL import Image

# ============================
# CONFIGURAÇÕES DA BANDEJA
# ============================
# Lâminas dispostas verticalmente: largura menor em X, altura maior em Y
SLIDE_WIDTH_X = 26.0   # largura da lâmina (eixo X)
SLIDE_HEIGHT_Y = 77.0  # altura da lâmina (eixo Y)

COL_SPACING = 15.0
ROW_SPACING = 10.0
LEFT_MARGIN = 15.0
TOP_MARGIN = 10.0

COLS = 8
ROWS = 2
N_POSICOES = COLS * ROWS  # 16

positions_mm = []
for row in range(ROWS):
    for col in range(COLS):
        x = LEFT_MARGIN + col * (SLIDE_WIDTH_X + COL_SPACING) + SLIDE_WIDTH_X / 2
        y = TOP_MARGIN + row * (SLIDE_HEIGHT_Y + ROW_SPACING) + SLIDE_HEIGHT_Y / 2
        positions_mm.append((round(x, 2), round(y, 2)))

# ============================
# ALGORITMOS
# ============================
def original_order(pontos):
    return list(range(len(pontos)))

def nearest_neighbor(pontos, inicio=(0, 0)):
    if not pontos:
        return []
    nao_visitados = list(range(len(pontos)))
    ordem = []
    atual = inicio
    while nao_visitados:
        idx = min(nao_visitados, key=lambda i: math.hypot(pontos[i][0] - atual[0],
                                                          pontos[i][1] - atual[1]))
        ordem.append(idx)
        atual = pontos[idx]
        nao_visitados.remove(idx)
    return ordem

def nearest_insertion(pontos, inicio=(0, 0)):
    if len(pontos) <= 1:
        return list(range(len(pontos)))
    dist_inicio = [math.hypot(p[0], p[1]) for p in pontos]
    primeiro = min(range(len(pontos)), key=lambda i: dist_inicio[i])
    ordem = [primeiro]
    nao_inseridos = list(range(len(pontos)))
    nao_inseridos.remove(primeiro)

    while nao_inseridos:
        melhor_ponto = None
        melhor_posicao = None
        menor_custo = float('inf')
        for p in nao_inseridos:
            for i in range(len(ordem)):
                prev = ordem[i]
                nxt = ordem[(i + 1) % len(ordem)]
                custo = (math.hypot(pontos[p][0] - pontos[prev][0], pontos[p][1] - pontos[prev][1]) +
                         math.hypot(pontos[p][0] - pontos[nxt][0], pontos[p][1] - pontos[nxt][1]) -
                         math.hypot(pontos[prev][0] - pontos[nxt][0], pontos[prev][1] - pontos[nxt][1]))
                if custo < menor_custo:
                    menor_custo = custo
                    melhor_ponto = p
                    melhor_posicao = i + 1
        ordem.insert(melhor_posicao, melhor_ponto)
        nao_inseridos.remove(melhor_ponto)
    return ordem

def two_opt(pontos, ordem):
    if len(ordem) < 3:
        return ordem
    improved = True
    while improved:
        improved = False
        for i in range(len(ordem) - 2):
            for j in range(i + 2, len(ordem)):
                a, b = ordem[i], ordem[i + 1]
                c, d = ordem[j], ordem[(j + 1) % len(ordem)]
                dist_before = (math.hypot(pontos[a][0] - pontos[b][0], pontos[a][1] - pontos[b][1]) +
                               math.hypot(pontos[c][0] - pontos[d][0], pontos[c][1] - pontos[d][1]))
                dist_after = (math.hypot(pontos[a][0] - pontos[c][0], pontos[a][1] - pontos[c][1]) +
                              math.hypot(pontos[b][0] - pontos[d][0], pontos[b][1] - pontos[d][1]))
                if dist_after < dist_before - 1e-9:
                    ordem[i + 1:j + 1] = reversed(ordem[i + 1:j + 1])
                    improved = True
                    break
            if improved:
                break
    return ordem

def genetic_algorithm(pontos, pop_size=50, generations=100, mutation_rate=0.02, inicio=(0, 0)):
    n = len(pontos)
    if n <= 1:
        return list(range(n))

    def distancia_total(ordem):
        if not ordem:
            return 0
        dist = math.hypot(pontos[ordem[0]][0] - inicio[0], pontos[ordem[0]][1] - inicio[1])
        for i in range(len(ordem) - 1):
            dist += math.hypot(pontos[ordem[i + 1]][0] - pontos[ordem[i]][0],
                               pontos[ordem[i + 1]][1] - pontos[ordem[i]][1])
        return dist

    populacao = [random.sample(range(n), n) for _ in range(pop_size)]
    melhor_ordem = min(populacao, key=distancia_total)
    melhor_dist = distancia_total(melhor_ordem)

    for _ in range(generations):
        fitness = [distancia_total(ind) for ind in populacao]
        nova_pop = []
        for _ in range(pop_size):
            a = random.randint(0, pop_size - 1)
            b = random.randint(0, pop_size - 1)
            pai1 = populacao[a] if fitness[a] < fitness[b] else populacao[b]
            a = random.randint(0, pop_size - 1)
            b = random.randint(0, pop_size - 1)
            pai2 = populacao[a] if fitness[a] < fitness[b] else populacao[b]
            filho = [-1] * n
            start = random.randint(0, n - 2)
            end = random.randint(start + 1, n - 1)
            for i in range(start, end + 1):
                filho[i] = pai1[i]
            idx = 0
            for gene in pai2:
                if gene not in filho:
                    while filho[idx] != -1:
                        idx += 1
                    filho[idx] = gene
            if random.random() < mutation_rate:
                i, j = random.sample(range(n), 2)
                filho[i], filho[j] = filho[j], filho[i]
            nova_pop.append(filho)
        populacao = nova_pop
        melhor_atual = min(populacao, key=distancia_total)
        dist_atual = distancia_total(melhor_atual)
        if dist_atual < melhor_dist:
            melhor_dist = dist_atual
            melhor_ordem = melhor_atual[:]
    return melhor_ordem

def simulated_annealing(pontos, initial_temp=1000, cooling_rate=0.995, iterations=2000, inicio=(0, 0)):
    n = len(pontos)
    if n <= 1:
        return list(range(n))

    def distancia_total(ordem):
        if not ordem:
            return 0
        dist = math.hypot(pontos[ordem[0]][0] - inicio[0], pontos[ordem[0]][1] - inicio[1])
        for i in range(len(ordem) - 1):
            dist += math.hypot(pontos[ordem[i + 1]][0] - pontos[ordem[i]][0],
                               pontos[ordem[i + 1]][1] - pontos[ordem[i]][1])
        return dist

    solucao_atual = random.sample(range(n), n)
    custo_atual = distancia_total(solucao_atual)
    melhor_solucao = solucao_atual[:]
    melhor_custo = custo_atual
    temp = initial_temp
    for _ in range(iterations):
        i, j = random.sample(range(n), 2)
        nova_solucao = solucao_atual[:]
        nova_solucao[i], nova_solucao[j] = nova_solucao[j], nova_solucao[i]
        novo_custo = distancia_total(nova_solucao)
        delta = novo_custo - custo_atual
        if delta < 0 or random.random() < math.exp(-delta / temp):
            solucao_atual = nova_solucao
            custo_atual = novo_custo
            if custo_atual < melhor_custo:
                melhor_custo = custo_atual
                melhor_solucao = solucao_atual[:]
        temp *= cooling_rate
        if temp < 0.01:
            break
    return melhor_solucao

def brute_force(pontos, inicio=(0, 0)):
    n = len(pontos)
    if n > 10:
        return None
    if n == 0:
        return []
    melhor_ordem = None
    melhor_dist = float('inf')
    for perm in permutations(range(n)):
        dist = 0
        atual = inicio
        for i in perm:
            dist += math.hypot(pontos[i][0] - atual[0], pontos[i][1] - atual[1])
            atual = pontos[i]
        if dist < melhor_dist:
            melhor_dist = dist
            melhor_ordem = list(perm)
    return melhor_ordem

ALGORITMOS = {
    "Ordem Original": original_order,
    "Vizinho Mais Próximo": nearest_neighbor,
    "Inserção Mais Próxima": nearest_insertion,
    "2-opt/Sobre NN (Nearest Neighbor)": lambda pontos: two_opt(pontos, nearest_neighbor(pontos)),
    "2-opt/Sobre inserção (Nearest Insertion)": lambda pontos: two_opt(pontos, nearest_insertion(pontos)),
    "Algoritmo Genético": genetic_algorithm,
    "Simulated Annealing": simulated_annealing,
    "Força Bruta": brute_force
}

# ============================
# FUNÇÃO PARA GERAR IMAGEM DA BANDEJA
# ============================
def gerar_imagem_bandeja(positions, sensor_str, ordem, pos_atual_idx=None,
                         max_step=None, titulo=""):
    fig, ax = plt.subplots(figsize=(10, 4))

    for i, (x, y) in enumerate(positions):
        ocupado = (sensor_str[i] == '1') if i < len(sensor_str) else False
        cor = 'green' if ocupado else 'lightgray'
        rect = patches.Rectangle(
            (x - SLIDE_WIDTH_X / 2, y - SLIDE_HEIGHT_Y / 2),
            SLIDE_WIDTH_X,
            SLIDE_HEIGHT_Y,
            linewidth=1,
            edgecolor='black',
            facecolor=cor,
            alpha=0.8
        )
        ax.add_patch(rect)
        ax.text(x, y, str(i + 1), ha='center', va='center', fontsize=6, color='black')

    if max_step is None:
        max_step = len(ordem) if ordem else 0
    else:
        max_step = min(max_step, len(ordem))

    if ordem and max_step > 0:
        pts = [(0, 0)] + [positions[i] for i in ordem[:max_step]]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, 'b-', linewidth=2, alpha=0.6, label='Rota percorrida')

    ax.plot(0, 0, 'go', markersize=8, label='Origem (0,0)')

    if pos_atual_idx is not None and ordem and pos_atual_idx < len(ordem):
        x_atual, y_atual = positions[ordem[pos_atual_idx]]
        ax.plot(x_atual, y_atual, 'ro', markersize=12, label='Posição atual')

    ax.invert_yaxis()

    xs_all = [p[0] for p in positions]
    ys_all = [p[1] for p in positions]
    x_max_plot = max(xs_all) + SLIDE_WIDTH_X / 2 + 30
    y_max_plot = max(ys_all) + SLIDE_HEIGHT_Y / 2 + 30

    ax.set_xlim(-20, x_max_plot)
    ax.set_ylim(y_max_plot, -20)
    ax.set_aspect('equal')
    ax.set_title(titulo, fontsize=10)
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.legend(loc='upper right', fontsize=8)
    ax.set_xlabel('X (mm)', fontsize=8)
    ax.set_ylabel('Y (mm)', fontsize=8)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img = Image.open(buf)
    plt.close(fig)
    return img

# ============================
# GRÁFICO COMPARATIVO (BARRAS HORIZONTAIS)
# ============================
def grafico_comparativo(resultados):
    """
    resultados: lista de dicts com chaves 'algoritmo', 'tempo', 'distancia'
    Retorna uma figura matplotlib com barras horizontais ordenadas por distância.
    Anota o gap % em relação ao melhor resultado (menor distância).
    """
    # Ordena por distância crescente (melhor -> pior)
    resultados_ord = sorted(resultados, key=lambda r: r['distancia'])
    nomes = [r['algoritmo'] for r in resultados_ord]
    distancias = [r['distancia'] for r in resultados_ord]

    melhor_dist = min(distancias)

    fig, ax = plt.subplots(figsize=(10, max(3, 0.5 * len(nomes) + 1)))
    cores = plt.cm.viridis(np.linspace(0.15, 0.85, len(nomes)))
    bars = ax.barh(nomes, distancias, color=cores, edgecolor='black')

    # Anotação de valor + gap
    for bar, val in zip(bars, distancias):
        gap = (val - melhor_dist) / melhor_dist * 100 if melhor_dist > 0 else 0
        if abs(gap) < 1e-6:
            txt = f"{val:.2f} mm  (ótimo)"
        else:
            txt = f"{val:.2f} mm  (+{gap:.1f}%)"
        ax.text(bar.get_width() + max(distancias) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                txt, va='center', fontsize=8)

    ax.invert_yaxis()  # melhor no topo
    ax.set_xlabel("Distância total (mm)", fontsize=9)
    ax.set_title("Comparação de Algoritmos — Distância percorrida\n(ordenado do melhor para o pior)", fontsize=11)
    ax.grid(axis='x', linestyle='--', alpha=0.4)
    ax.set_xlim(0, max(distancias) * 1.25)

    fig.tight_layout()
    return fig

# ============================
# GERADOR DE SENSORES
# ============================
def gerar_sensores(seed=None, num_ocupados=10):
    if seed is not None:
        random.seed(seed)
    indices = random.sample(range(N_POSICOES), min(num_ocupados, N_POSICOES))
    s = ['0'] * N_POSICOES
    for i in indices:
        s[i] = '1'
    return ''.join(s)

# ============================
# FUNÇÃO PARA CALCULAR DISTÂNCIA TOTAL
# ============================
def distancia_total_rota(pontos, ordem, inicio=(0, 0)):
    if not ordem:
        return 0
    dist = math.hypot(pontos[ordem[0]][0] - inicio[0], pontos[ordem[0]][1] - inicio[1])
    for i in range(len(ordem) - 1):
        dist += math.hypot(pontos[ordem[i + 1]][0] - pontos[ordem[i]][0],
                           pontos[ordem[i + 1]][1] - pontos[ordem[i]][1])
    return dist

# ============================
# INTERFACE STREAMLIT
# ============================
st.set_page_config(layout="wide")

# ============================
# CSS CUSTOMIZADO
# ============================
st.markdown("""
    <style>
        .main > div:first-child {
            padding-top: 0px;
        }
        h1 {
            font-size: 1.8rem !important;
            margin-top: -20px !important;
            margin-bottom: 5px !important;
        }
        .sidebar .sidebar-content {
            padding-top: 10px;
        }
        .block-container {
            padding-top: 3rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.header("📊 Comparação de Algoritmos")

def reset_estado():
    """Limpa o estado da simulação atual, mas preserva o histórico de comparações."""
    for key in ['ordem', 'sensor_str', 'passo', 'finalizado', 'tempo_total',
                'inicio_animacao', 'distancia_total', 'tempo_calculo']:
        if key in st.session_state:
            del st.session_state[key]

algoritmo_nome = st.sidebar.selectbox(
    "Algoritmo",
    list(ALGORITMOS.keys()),
    on_change=reset_estado
)
seed = st.sidebar.number_input("Seed (para gerar sensores)", value=42, step=1)
num_ocupados = st.sidebar.slider("Número de lâminas ocupadas", 1, N_POSICOES, 10)
velocidade = st.sidebar.slider("Velocidade da animação (segundos/passo)",
                               0.05, 1.5, 0.3, 0.05)

# Botão para limpar histórico
if 'historico' not in st.session_state:
    st.session_state['historico'] = []

if st.sidebar.button("🧹 Limpar histórico de comparações"):
    st.session_state['historico'] = []
    st.rerun()

with st.sidebar.expander("📖 Sobre os Algoritmos", expanded=False):
    st.markdown("""
    **Ordem Original** – percorre as lâminas na ordem fixa (linha a linha).  
    *Baseline para comparação.*

    **Vizinho Mais Próximo** – heurística gulosa: sempre vai para a lâmina mais próxima da posição atual.  
    *Rápido, mas pode criar cruzamentos.*

    **Inserção Mais Próxima** – constrói a rota inserindo cada lâmina na posição que menos aumenta a distância total.  
    *Gera rotas iniciais melhores que o Vizinho Mais Próximo.*

    **2-opt/Sobre NN** – aplica a melhoria local 2-opt sobre a rota gerada pelo Vizinho Mais Próximo.  
    *Elimina cruzamentos e reduz distância, mas depende da rota inicial.*

    **2-opt/Sobre Inserção** – aplica o 2-opt sobre a rota gerada pela Inserção Mais Próxima.  
    *Parte de uma base melhor, resultando em rotas finais superiores – é a recomendação prática.*

    **Algoritmo Genético** – evolui uma população de rotas usando seleção, crossover (OX) e mutação.  
    *Encontra soluções de alta qualidade, porém mais lento.*

    **Simulated Annealing** – aceita pioras com probabilidade decrescente para escapar de ótimos locais.  
    *Robusto e de boa qualidade, sensível aos parâmetros.*

    **Força Bruta** – testa todas as permutações possíveis (exato).  
    *Só viável para até 10 lâminas.*

    💡 **Diferença entre os 2-opts**:  
    Ambos usam a mesma técnica de melhoria local, mas **2-opt/Sobre Inserção** parte de uma rota inicial de melhor qualidade, portanto tende a encontrar rotas finais mais curtas.
    """)

if st.sidebar.button("🚀 Iniciar Scan"):
    reset_estado()
    sensor_str = gerar_sensores(seed=seed, num_ocupados=num_ocupados)
    indices_ocupados = [i for i, ch in enumerate(sensor_str) if ch == '1']
    pontos = [positions_mm[i] for i in indices_ocupados]

    if not pontos:
        sensor_str = '1' * N_POSICOES
        indices_ocupados = list(range(N_POSICOES))
        pontos = positions_mm

    funcao_algoritmo = ALGORITMOS[algoritmo_nome]
    start_time = time.time()

    if algoritmo_nome == "Força Bruta":
        ordem_relativa = funcao_algoritmo(pontos)
        if ordem_relativa is None:
            st.warning("Força Bruta só suporta até 10 lâminas. Usando Vizinho Mais Próximo.")
            ordem_relativa = nearest_neighbor(pontos)
    else:
        ordem_relativa = funcao_algoritmo(pontos)

    tempo_calculo = time.time() - start_time
    ordem_original = [indices_ocupados[i] for i in ordem_relativa]
    dist_total = distancia_total_rota(pontos, ordem_relativa)

    st.session_state['sensor_str'] = sensor_str
    st.session_state['ordem'] = ordem_original
    st.session_state['algoritmo'] = algoritmo_nome
    st.session_state['tempo_calculo'] = tempo_calculo
    st.session_state['distancia_total'] = dist_total
    st.session_state['velocidade'] = velocidade
    st.session_state['passo'] = 0
    st.session_state['finalizado'] = False
    st.session_state['inicio_animacao'] = time.time()
    st.rerun()

# --- ÁREA PRINCIPAL ---
if 'ordem' in st.session_state and st.session_state.get('ordem', None) is not None:
    ordem = st.session_state['ordem']
    sensor_str = st.session_state['sensor_str']
    passo = st.session_state.get('passo', 0)
    finalizado = st.session_state.get('finalizado', False)
    algoritmo_nome = st.session_state['algoritmo']

    if not finalizado:
        # Animação passo a passo
        placeholder = st.empty()
        total_passos = len(ordem)
        for i in range(passo, total_passos):
            titulo = f"{algoritmo_nome} - Passo {i + 1}/{total_passos}"
            img = gerar_imagem_bandeja(
                positions_mm,
                sensor_str,
                ordem,
                pos_atual_idx=i,
                max_step=i + 1,
                titulo=titulo
            )
            placeholder.image(img, width=800)
            time.sleep(velocidade)
            st.session_state['passo'] = i + 1

        st.session_state['finalizado'] = True
        st.session_state['tempo_total'] = time.time() - st.session_state['inicio_animacao']
        st.rerun()

    else:
        # Estado final: imagem + métricas
        img = gerar_imagem_bandeja(
            positions_mm,
            sensor_str,
            ordem,
            pos_atual_idx=None,
            max_step=None,
            titulo=f"{algoritmo_nome} - Concluído!"
        )
        st.image(img, width=800)

        # Registra o resultado no histórico (uma entrada por algoritmo)
        entrada = {
            'algoritmo': algoritmo_nome,
            'tempo': st.session_state.get('tempo_total', 0),
            'distancia': st.session_state.get('distancia_total', 0),
            'seed': int(seed),
            'num_ocupados': int(num_ocupados),
        }
        # Substitui se já houver entrada deste algoritmo com a mesma seed/num_ocupados
        historico = st.session_state['historico']
        historico = [
            h for h in historico
            if not (h['algoritmo'] == entrada['algoritmo']
                    and h['seed'] == entrada['seed']
                    and h['num_ocupados'] == entrada['num_ocupados'])
        ]
        historico.append(entrada)
        st.session_state['historico'] = historico

        # Métricas resumidas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.success("✅ Scan concluído!")
        with col2:
            st.metric("Lâminas ocupadas", len(ordem))
        with col3:
            st.metric("Tempo total", f"{st.session_state.get('tempo_total', 0):.2f} s")
        with col4:
            st.metric("Distância total", f"{st.session_state.get('distancia_total', 0):.2f} mm")

        # ============================
        # COMPARAÇÃO DE ALGORITMOS
        # ============================
        st.markdown("---")
        st.subheader("📊 Comparação de Algoritmos")

        if st.session_state['historico']:
            # Filtra entradas que correspondem à seed/num_ocupados atual
            hist_filtrado = [
                h for h in st.session_state['historico']
                if h['seed'] == int(seed) and h['num_ocupados'] == int(num_ocupados)
            ]

            if len(hist_filtrado) < 2:
                st.info(
                    "ℹ️ Execute o mesmo cenário (mesma seed e número de lâminas ocupadas) "
                    "com outros algoritmos para ver a comparação. "
                    "A comparação exige pelo menos 2 algoritmos rodados no mesmo cenário."
                )
            else:
                # Gráfico
                fig = grafico_comparativo(hist_filtrado)
                st.pyplot(fig)

                # Tabela ordenada (Tempo → Distância)
                st.markdown("**Tabela de resultados (cenário atual):**")
                linhas = sorted(
                    hist_filtrado,
                    key=lambda h: (round(h['distancia'], 2), h['tempo'])
                )
                tabela_md = "| Algoritmo | Tempo (s) | Distância (mm) |\n|---|---|---|\n"
                melhor = min(h['distancia'] for h in linhas)
                for h in linhas:
                    gap = (h['distancia'] - melhor) / melhor * 100 if melhor > 0 else 0
                    gap_str = "—" if abs(gap) < 1e-6 else f"+{gap:.1f}%"
                    tabela_md += f"| {h['algoritmo']} | {h['tempo']:.2f} | {h['distancia']:.2f} ({gap_str}) |\n"
                st.markdown(tabela_md)

        else:
            st.info("ℹ️ Ainda não há resultados no histórico. Execute um scan para começar.")

        if st.button("🔄 Nova Simulação"):
            reset_estado()
            st.rerun()

else:
    # Estado inicial
    sensor_exemplo = gerar_sensores(seed=42, num_ocupados=10)
    img = gerar_imagem_bandeja(
        positions_mm,
        sensor_exemplo,
        [],
        pos_atual_idx=None,
        max_step=0,
        titulo="Aguardando início"
    )
    st.image(img, width=800)

    # Se já houver histórico, mostra o gráfico comparativo mesmo antes de rodar
    if st.session_state.get('historico'):
        st.markdown("---")
        st.subheader("📊 Comparação de Algoritmos (histórico)")
        hist_filtrado = [
            h for h in st.session_state['historico']
            if h['seed'] == int(seed) and h['num_ocupados'] == int(num_ocupados)
        ]
        if len(hist_filtrado) >= 2:
            fig = grafico_comparativo(hist_filtrado)
            st.pyplot(fig)
        else:
            st.info("ℹ️ Selecione outro algoritmo com os mesmos parâmetros para comparar.")

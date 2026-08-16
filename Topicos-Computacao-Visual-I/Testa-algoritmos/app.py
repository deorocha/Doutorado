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
SLIDE_LEN_X = 77.0
SLIDE_WID_Y = 26.0
COL_SPACING = 15.0
ROW_SPACING = 10.0
LEFT_MARGIN = 15.0
TOP_MARGIN = 10.0
COLS = 4
ROWS = 8

positions_mm = []
for row in range(ROWS):
    for col in range(COLS):
        x = LEFT_MARGIN + col * (SLIDE_LEN_X + COL_SPACING) + SLIDE_LEN_X / 2
        y = TOP_MARGIN + row * (SLIDE_WID_Y + ROW_SPACING) + SLIDE_WID_Y / 2
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
                nxt = ordem[(i+1) % len(ordem)]
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
        for i in range(len(ordem)-1):
            dist += math.hypot(pontos[ordem[i+1]][0] - pontos[ordem[i]][0],
                               pontos[ordem[i+1]][1] - pontos[ordem[i]][1])
        return dist

    populacao = [random.sample(range(n), n) for _ in range(pop_size)]
    melhor_ordem = min(populacao, key=distancia_total)
    melhor_dist = distancia_total(melhor_ordem)

    for _ in range(generations):
        fitness = [distancia_total(ind) for ind in populacao]
        nova_pop = []
        for _ in range(pop_size):
            a = random.randint(0, pop_size-1)
            b = random.randint(0, pop_size-1)
            pai1 = populacao[a] if fitness[a] < fitness[b] else populacao[b]
            a = random.randint(0, pop_size-1)
            b = random.randint(0, pop_size-1)
            pai2 = populacao[a] if fitness[a] < fitness[b] else populacao[b]
            filho = [-1]*n
            start = random.randint(0, n-2)
            end = random.randint(start+1, n-1)
            for i in range(start, end+1):
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
        for i in range(len(ordem)-1):
            dist += math.hypot(pontos[ordem[i+1]][0] - pontos[ordem[i]][0],
                               pontos[ordem[i+1]][1] - pontos[ordem[i]][1])
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
# FUNÇÃO PARA GERAR IMAGEM
# ============================
def gerar_imagem_bandeja(positions, sensor_str, ordem, pos_atual_idx=None,
                         max_step=None, titulo=""):
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, (x, y) in enumerate(positions):
        ocupado = (sensor_str[i] == '1') if i < len(sensor_str) else False
        cor = 'green' if ocupado else 'lightgray'
        rect = patches.Rectangle((x - SLIDE_LEN_X/2, y - SLIDE_WID_Y/2),
                                 SLIDE_LEN_X, SLIDE_WID_Y,
                                 linewidth=1, edgecolor='black',
                                 facecolor=cor, alpha=0.8)
        ax.add_patch(rect)
        ax.text(x, y, str(i+1), ha='center', va='center', fontsize=6, color='black')

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
    ax.set_xlim(-20, 420)
    ax.set_ylim(320, -20)
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
# GERADOR DE SENSORES
# ============================
def gerar_sensores(seed=None, num_ocupados=20):
    if seed is not None:
        random.seed(seed)
    indices = random.sample(range(32), min(num_ocupados, 32))
    s = ['0'] * 32
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
    for i in range(len(ordem)-1):
        dist += math.hypot(pontos[ordem[i+1]][0] - pontos[ordem[i]][0],
                           pontos[ordem[i+1]][1] - pontos[ordem[i]][1])
    return dist

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
            padding-top: 10px !important;
        }
    </style>
""", unsafe_allow_html=True)

# INTERFACE STREAMLIT
st.set_page_config(layout="wide")
# st.title("📊 Comparação de Algoritmos")

# SIDEBAR
st.sidebar.header("📊 Comparação de Algoritmos")
# st.sidebar.header("⚙️ Configurações")

def reset_estado():
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
num_ocupados = st.sidebar.slider("Número de lâminas ocupadas", 1, 32, 20)
velocidade = st.sidebar.slider("Velocidade da animação (segundos/passo)",
                               0.05, 1.5, 0.3, 0.05)

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
        sensor_str = '1' * 32
        indices_ocupados = list(range(32))
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

# --- ÁREA PRINCIPAL (ANIMAÇÃO SEM PISCA-PISCA) ---
if 'ordem' in st.session_state and st.session_state.get('ordem', None) is not None:
    ordem = st.session_state['ordem']
    sensor_str = st.session_state['sensor_str']
    passo = st.session_state.get('passo', 0)
    finalizado = st.session_state.get('finalizado', False)
    algoritmo_nome = st.session_state['algoritmo']

    if not finalizado:
        # Se ainda não completou a animação, executa o loop aqui mesmo
        placeholder = st.empty()
        total_passos = len(ordem)
        for i in range(passo, total_passos):
            # Gera imagem do passo atual
            titulo = f"{algoritmo_nome} - Passo {i+1}/{total_passos}"
            img = gerar_imagem_bandeja(positions_mm, sensor_str, ordem,
                                       pos_atual_idx=i,
                                       max_step=i+1,
                                       titulo=titulo)
            placeholder.image(img, use_container_width=False, width=700)
            time.sleep(velocidade)
            # Atualiza o passo no estado (para caso haja interrupção)
            st.session_state['passo'] = i + 1

        # Fim da animação
        st.session_state['finalizado'] = True
        st.session_state['tempo_total'] = time.time() - st.session_state['inicio_animacao']
        st.rerun()  # recarrega para mostrar o estado final com métricas

    else:
        # Estado final: exibe a imagem completa e as métricas
        img = gerar_imagem_bandeja(positions_mm, sensor_str, ordem,
                                   pos_atual_idx=None,
                                   max_step=None,
                                   titulo=f"{algoritmo_nome} - Concluído!")
        st.image(img, use_container_width=False, width=700)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.success("✅ Scan concluído!")
        with col2:
            st.metric("Lâminas ocupadas", len(ordem))
        with col3:
            # <-- SUBSTITUÍDO "Tempo de cálculo" POR "Tempo total" E USANDO O VALOR DE tempo_total
            st.metric("Tempo total", f"{st.session_state.get('tempo_total', 0):.2f} s")
        with col4:
            st.metric("Distância total", f"{st.session_state.get('distancia_total', 0):.2f} mm")

        if st.button("🔄 Nova Simulação"):
            reset_estado()
            st.rerun()

else:
    # Estado inicial
    sensor_exemplo = gerar_sensores(seed=42, num_ocupados=20)
    img = gerar_imagem_bandeja(positions_mm, sensor_exemplo, [],
                               pos_atual_idx=None,
                               max_step=0,
                               titulo="Aguardando início")
    st.image(img, use_container_width=False, width=700)

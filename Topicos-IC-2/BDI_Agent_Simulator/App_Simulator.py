import streamlit as st
import os
import re
import time
import datetime
from queue import Queue, Empty

# CSS personalizado - corrigindo o sidebar
st.markdown("""
<style>
    /* Remover TODAS as margens e paddings de TODOS os elementos */
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    /* Container principal do Streamlit */
    .main .block-container {
        padding-top: 0px !important;
        padding-bottom: 0px !important;
        padding-left: 0px !important;
        padding-right: 0px !important;
        max-width: 100% !important;
    }
    
    /* MANTER o header visível para o botão do sidebar */
    /* header {
        display: none !important;
    } */
    
    /* Remover margens do título */
    h1, h2, h3, h4, h5, h6 {
        margin-top: 15px !important;
        margin-bottom: 15px !important;
        padding: 5px !important;
    }

    /* Remover margens de todos os elementos do Streamlit */
    .stApp {
        margin: 0px !important;
        padding: 0px !important;
    }
    
    /* Ajustar file uploader */
    .stFileUploader {
        margin: 0px !important;
        padding: 0px !important;
    }
    
    /* Ajustar botões */
    .stButton button {
        margin: 10px !important;
        padding: 5px 10px !important;
    }
    
    /* Ajustar colunas */
    .stColumns {
        margin: 0px !important;
        padding: 0px !important;
    }
    
    /* Ajustar expanders */
    .streamlit-expander {
        margin: 0px !important;
        padding: 0px !important;
    }

    /* Espaço ANTES do primeiro expander (acima) */
    div[data-testid="stExpander"]:first-child {
        margin-top: 0.5rem !important;  /* ← AJUSTE AQUI: espaço acima do primeiro expander */
    }

    /* Espaço ENTRE expanders */
    div[data-testid="stExpander"] {
        margin-top: 0.3rem !important;    /* ← AJUSTE AQUI: espaço acima de cada expander */
        margin-bottom: 0.3rem !important;  /* ← AJUSTE AQUI: espaço abaixo de cada expander */
    }
    
    /* Espaço DEPOIS do último expander (abaixo) */
    div[data-testid="stExpander"]:last-child {
        margin-bottom: 0.5rem !important; /* ← AJUSTE AQUI: espaço abaixo do último expander */
    }
    
    div[data-testid="stExpander"] details {
        margin: 0px !important;
        padding: 0px !important;
    }
    
    div[data-testid="stExpander"] details summary {
        margin: 0px !important;
        padding: 5px !important;
    }
    
    div[data-testid="stExpander"] details summary p {
        font-family: 'Courier New' !important;
        font-size: 14px !important;
        font-weight: bold !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    div[data-testid="stExpander"] details div {
        margin: 0px !important;
        padding: 0px !important;
    }
    
    div[data-testid="stExpander"] pre {
        font-size: 10px !important;
        max-height: 350px !important;
        overflow-y: auto !important;
        margin: 0 !important;
        padding: 5px !important;
    }
    
    /* Containers de log */
    .log-container {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 5px;
        padding: 5px;
        max-height: 400px;
        overflow-y: auto;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        white-space: pre-wrap;
        margin: 0 !important;
    }
    
    /* Histórico dos agentes */
    .agent-history {
        font-family: 'Courier New', monospace;
        font-size: 11px;
        background-color: white;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 5px;
        max-height: 500px;
        overflow-y: auto;
        white-space: pre;
        margin: 0 !important;
    }
    
    /* Sidebar - manter visível e ajustar */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #dee2e6;
    }
    
    .css-1d391kg, .css-1lcbmhc, .css-1outpf7 {
        padding: 5px !important;
        margin: 0px !important;
    }
    
    /* Botão do sidebar */
    .css-1v0mbdj {
        margin: 0px !important;
        padding: 0px !important;
    }
    
    /* Alertas e mensagens */
    .stAlert, .stSuccess, .stInfo, .stWarning, .stError {
        margin: 2px 0 !important;
        padding: 5px !important;
    }
    
    /* Espaçamento entre seções */
    .element-container {
        margin: 0px !important;
        padding: 0px !important;
    }
    
    /* Remover qualquer padding residual */
    div[data-testid="stVerticalBlock"] {
        gap: 0rem !important;
    }
    
    /* Ajustar o header para ser mínimo */
    header .decoration {
        display: none;
    }
    
    /* Manter o botão do sidebar visível */
    .css-1vq4p4l {
        padding: 0px !important;
        margin: 0px !important;
    }
    
    /* Ajustar o conteúdo principal para compensar a barra lateral */
    .main .block-container {
        padding-left: 1rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Configuração da página para layout wide
st.set_page_config(
    page_title="Simulador MAS2J",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# [O resto do código permanece exatamente igual...]

# Inicializar estado da aplicação
if 'simulation_running' not in st.session_state:
    st.session_state.simulation_running = False
if 'simulation_started' not in st.session_state:
    st.session_state.simulation_started = False
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'agents_state' not in st.session_state:
    st.session_state.agents_state = {}
if 'agents_history' not in st.session_state:
    st.session_state.agents_history = {}
if 'simulators' not in st.session_state:
    st.session_state.simulators = {}
if 'last_update' not in st.session_state:
    st.session_state.last_update = 0

# Fila para comunicação
log_queue = Queue()

def log_message(agent_name, message):
    """Adiciona mensagem à fila de logs"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_queue.put(f"[{timestamp}] {agent_name}: {message}")

def add_agent_history(agent_name, cycle, beliefs, goals):
    """Adiciona um registro ao histórico do agente"""
    if agent_name not in st.session_state.agents_history:
        st.session_state.agents_history[agent_name] = []
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.agents_history[agent_name].append({
        'time': timestamp,
        'cycle': cycle,
        'beliefs': beliefs,
        'goals': goals
    })
    
    # Manter apenas os últimos 50 registros por agente
    if len(st.session_state.agents_history[agent_name]) > 50:
        st.session_state.agents_history[agent_name].pop(0)

class AgentSimulator:
    """Simula o comportamento de agentes BDI baseado nos arquivos .asl"""
    
    def __init__(self, name, asl_file):
        self.name = name
        self.asl_file = asl_file
        self.cycle = 0
        self.position = (0, 0)
        self.lixos_coletados = 0
        self.moeda_encontrada = False
        self.last_cycle_time = 0
        
    def simulate_cycle(self):
        """Executa um ciclo de simulação do agente"""
        current_time = time.time()
        
        # Só executa um ciclo a cada 3 segundos
        if current_time - self.last_cycle_time < 3:
            return None
            
        self.cycle += 1
        self.last_cycle_time = current_time
        
        # Comportamento baseado no ciclo e no tipo de agente
        if self.name == "r1":
            return self._simulate_r1()
        elif self.name == "r2":
            return self._simulate_r2()
        else:
            return self._simulate_generic()
    
    def _simulate_r1(self):
        """Simula o comportamento do agente r1 (coletor)"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if self.cycle == 1:
            log_message(self.name, "Iniciando limpeza do ambiente - Modo Exploratório")
            beliefs = "pos(0,0), r2_pos(3,3)"
            goals = "!iniciar_limpeza, !explorar_sistematicamente"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle == 2:
            log_message(self.name, "Explorando ambiente a partir de (0,0)")
            self.position = (1, 1)
            beliefs = f"pos(1,1), visitado(0,0), r2_pos(3,3)"
            goals = "!encontrar_proxima_posicao, !navegar_para"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle == 3:
            log_message(self.name, "Encontrou lixo na posição (2,2) - coletando")
            self.position = (2, 2)
            self.lixos_coletados += 1
            beliefs = f"pos(2,2), lixo_na_posicao, lixo_coletado(2,2), visitado(1,1)"
            goals = "!processar_lixo, !navegar_para(3,3)"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle == 4:
            log_message(self.name, "Navegando para incinerador em (3,3)")
            self.position = (3, 3)
            beliefs = f"pos(3,3), lixo_coletado(2,2), r2_pos(3,3)"
            goals = "!entregar_lixo, !cooperar_com_r2"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle == 5:
            log_message(self.name, "Lixo entregue ao R2 - continuando exploração")
            self.position = (4, 4)
            beliefs = f"pos(4,4), lixo_coletado(2,2), r2_pos(3,3)"
            goals = "!procurar_mais_lixos, !encontrar_moeda"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif 6 <= self.cycle <= 15:
            # Ciclos de exploração contínua
            x, y = (self.cycle % 5, (self.cycle + 1) % 5)
            self.position = (x, y)
            
            if self.cycle == 8 and not self.moeda_encontrada:
                log_message(self.name, f"Moeda encontrada na posição ({x},{y})!")
                self.moeda_encontrada = True
                beliefs = f"pos({x},{y}), lixo_coletado(2,2), moeda_encontrada({x},{y})"
                goals = "!coletar_moeda, !finalizar_missao"
                add_agent_history(self.name, self.cycle, beliefs, goals)
                return {'crencas': beliefs, 'metas': goals}
            else:
                log_message(self.name, f"Explorando posição ({x},{y}) - Ciclo {self.cycle-5}")
                beliefs = f"pos({x},{y}), lixo_coletado(2,2){', moeda_encontrada' if self.moeda_encontrada else ''}"
                goals = "!explorar_sistematicamente, !encontrar_proxima_posicao"
                add_agent_history(self.name, self.cycle, beliefs, goals)
                return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle > 15:
            log_message(self.name, "Missão concluída com sucesso!")
            beliefs = f"pos({self.position[0]},{self.position[1]}), todos_lixos_coletados, moeda_coletada"
            goals = "!finalizar, !manter_posicao"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        return None
    
    def _simulate_r2(self):
        """Simula o comportamento do agente r2 (incinerador)"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if self.cycle == 1:
            log_message(self.name, "Incinerador ativo - aguardando lixo")
            beliefs = "pos(3,3)"
            goals = "!manter_posicao"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle == 4:
            log_message(self.name, "Recebendo lixo do R1 - incinerando")
            beliefs = "pos(3,3), lixo_para_incinerar"
            goals = "!incinerar_lixo"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle == 5:
            log_message(self.name, "Lixo incinerado com sucesso!")
            beliefs = "pos(3,3), lixo_incinerado"
            goals = "!aguardar_proximo_lixo"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        elif self.cycle <= 15:
            log_message(self.name, f"Aguardando próximo lixo... [Ciclo {self.cycle}]")
            beliefs = "pos(3,3)"
            goals = "!manter_posicao"
            add_agent_history(self.name, self.cycle, beliefs, goals)
            return {'crencas': beliefs, 'metas': goals}
        
        return None
    
    def _simulate_generic(self):
        """Simula comportamento genérico para outros agentes"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_message(self.name, f"Executando ciclo {self.cycle}")
        beliefs = f"pos({self.cycle % 4},{self.cycle % 3})"
        goals = "!executar_tarefa"
        add_agent_history(self.name, self.cycle, beliefs, goals)
        return {'crencas': beliefs, 'metas': goals}

def initialize_simulation(mas2j_content):
    """Inicializa a simulação"""
    try:
        # Extrair agentes do arquivo mas2j
        agentes = re.findall(r'agents:\s*((?:\s*\w+;)+)', mas2j_content)
        if not agentes:
            log_message("Sistema", "Nenhum agente encontrado no arquivo")
            return False
        
        nomes_agentes = re.findall(r'(\w+);', agentes[0])
        log_message("Sistema", f"Inicializando simulação para {len(nomes_agentes)} agentes")
        
        # Criar simuladores para cada agente
        st.session_state.simulators = {}
        st.session_state.agents_history = {}  # Resetar histórico
        
        for nome in nomes_agentes:
            asl_path = f"./src/asl/{nome}.asl"
            if os.path.exists(asl_path):
                st.session_state.simulators[nome] = AgentSimulator(nome, asl_path)
                st.session_state.agents_state[nome] = {
                    'crencas': "Inicializando...",
                    'metas': "Inicializando...",
                    'arquivo': asl_path
                }
                # Inicializar histórico vazio
                st.session_state.agents_history[nome] = []
                log_message("Sistema", f"Simulador criado para agente {nome}")
            else:
                log_message("Sistema", f"Arquivo {asl_path} não encontrado")
        
        log_message("Sistema", "Simulação inicializada com sucesso")
        return True
        
    except Exception as e:
        log_message("Sistema", f"Erro na inicialização: {str(e)}")
        import traceback
        log_message("Sistema", f"Traceback: {traceback.format_exc()}")
        return False

def run_simulation_cycle():
    """Executa um ciclo da simulação"""
    if not st.session_state.simulators:
        return False
    
    current_time = time.time()
    
    # Executar ciclo para cada agente
    for nome, simulator in st.session_state.simulators.items():
        state = simulator.simulate_cycle()
        if state:
            st.session_state.agents_state[nome] = {
                'crencas': state['crencas'],
                'metas': state['metas'],
                'arquivo': simulator.asl_file
            }
    
    # Verificar se todos os agentes completaram
    all_completed = all(simulator.cycle > 15 for simulator in st.session_state.simulators.values())
    
    if all_completed:
        log_message("Sistema", "Simulação concluída com sucesso!")
        return False
    
    return True

def start_simulation(mas2j_content):
    """Inicia a simulação"""
    if st.session_state.simulation_running:
        return
    
    st.session_state.simulation_running = True
    st.session_state.simulation_started = True
    st.session_state.logs = []
    st.session_state.agents_state = {}
    st.session_state.agents_history = {}
    st.session_state.simulators = {}
    
    if initialize_simulation(mas2j_content):
        log_message("Sistema", "Simulação iniciada")
    else:
        st.session_state.simulation_running = False
        log_message("Sistema", "Falha ao iniciar simulação")

def stop_simulation():
    """Para a simulação"""
    st.session_state.simulation_running = False
    st.session_state.simulation_started = False
    log_message("Sistema", "Simulação parada")

def format_history_line(time_str, cycle, beliefs, goals):
    """Formata uma linha do histórico com alinhamento fixo"""
    # Definir larguras das colunas
    time_width = 10
    cycle_width = 6
    beliefs_width = 60
    goals_width = 60
    
    # Formatar cada campo com a largura fixa
    time_formatted = time_str.ljust(time_width)
    cycle_formatted = str(cycle).ljust(cycle_width)
    beliefs_formatted = beliefs.ljust(beliefs_width)[:beliefs_width]
    goals_formatted = goals.ljust(goals_width)[:goals_width]
    
    return f"{time_formatted} {cycle_formatted} {beliefs_formatted} {goals_formatted}"

def render_agent_history(agent_name, asl_file):
    """Renderiza o histórico de um agente em formato de log alinhado"""
    if agent_name not in st.session_state.agents_history:
        st.info(f"Nenhum histórico disponível para {agent_name}")
        return
    
    history = st.session_state.agents_history[agent_name]
    
    # Criar cabeçalho
    header = format_history_line("Time", "Ciclo", "Crenças", "Metas")
    
    # Criar linhas do histórico
    history_lines = [header]
    for record in reversed(history):  # Mais recente primeiro
        line = format_history_line(
            record['time'], 
            record['cycle'], 
            record['beliefs'], 
            record['goals']
        )
        history_lines.append(line)
    
    # Juntar todas as linhas
    history_text = "\n".join(history_lines)
    
    # Exibir em um bloco de texto com formatação
    st.markdown(f'<div class="agent-history">{history_text}</div>', unsafe_allow_html=True)

# Interface principal
st.title("🤖 Simulador de Sistemas Multiagentes")

# Upload do arquivo .mas2j
arquivo = st.file_uploader("Selecione o arquivo .mas2j", type=['mas2j'])

mas2j_content = None
if arquivo:
    mas2j_content = arquivo.read().decode('utf-8')
    
    # Mostrar agentes detectados
    agentes = re.findall(r'agents:\s*((?:\s*\w+;)+)', mas2j_content)
    if agentes:
        nomes = re.findall(r'(\w+);', agentes[0])
        st.success(f"✅ {len(nomes)} agentes detectados: {', '.join(nomes)}")
        
        # Mostrar conteúdo dos arquivos ASL
        for nome in nomes:
            with st.expander(f"Agente: {nome}", expanded=False):
                try:
                    with open(f"./src/asl/{nome}.asl", 'r', encoding='utf-8') as f:
                        content = f.read()
                        st.code(content, language='python')
                except FileNotFoundError:
                    st.error(f"Arquivo ./src/asl/{nome}.asl não encontrado")
                except Exception as e:
                    st.error(f"Erro: {str(e)}")

# Controles de execução
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🚀 Executar Simulação", 
                 disabled=not mas2j_content or st.session_state.simulation_running,
                 type="primary"):
        start_simulation(mas2j_content)

with col2:
    if st.button("⏹️ Parar Simulação", 
                 disabled=not st.session_state.simulation_running):
        stop_simulation()

with col3:
    if st.button("🧹 Limpar Tudo"):
        st.session_state.logs = []
        st.session_state.agents_state = {}
        st.session_state.agents_history = {}
        st.session_state.simulators = {}
        st.session_state.simulation_running = False
        st.session_state.simulation_started = False

# Atualizar logs da fila
try:
    while True:
        log_entry = log_queue.get_nowait()
        st.session_state.logs.append(log_entry)
        if len(st.session_state.logs) > 100:
            st.session_state.logs.pop(0)
except Empty:
    pass

# Executar ciclo de simulação se estiver rodando
if st.session_state.simulation_running and st.session_state.simulation_started:
    should_continue = run_simulation_cycle()
    if not should_continue:
        st.session_state.simulation_running = False

# Mostrar logs em tempo real
st.subheader("📋 Logs de Execução")
if st.session_state.logs:
    logs_text = "\n".join(st.session_state.logs)
    st.markdown(f'<div class="log-container">{logs_text}</div>', unsafe_allow_html=True)
else:
    st.info("Nenhum log disponível. Execute a simulação para ver os logs.")

# Mostrar estado dos agentes em formato de histórico
st.subheader("🔍 Histórico dos Agentes")
if st.session_state.agents_history:
    for agent_name in st.session_state.agents_history.keys():
        asl_file = f"./src/asl/{agent_name}.asl"
        with st.expander(f"Agente {agent_name} ({asl_file})", expanded=True):
            render_agent_history(agent_name, asl_file)
else:
    st.info("Nenhum histórico disponível. Execute a simulação para ver o histórico dos agentes.")

# Indicador de status
st.sidebar.subheader("⚙️ Status do Sistema")
if st.session_state.simulation_running:
    st.sidebar.success("✅ Simulação em execução")
    if st.session_state.simulators:
        active_agents = len(st.session_state.simulators)
        completed_cycles = sum(simulator.cycle for simulator in st.session_state.simulators.values())
        st.sidebar.info(f"Agentes ativos: {active_agents}")
        st.sidebar.info(f"Ciclos completados: {completed_cycles}")
    
    # Auto-refresh quando a simulação estiver rodando
    time.sleep(2)
    st.rerun()
else:
    st.sidebar.info("⏸️ Simulação parada")

# Informações do sistema
st.sidebar.subheader("📊 Estatísticas")
if st.session_state.agents_history:
    total_records = sum(len(history) for history in st.session_state.agents_history.values())
    st.sidebar.write(f"Total de registros: {total_records}")
    for agent_name, history in st.session_state.agents_history.items():
        st.sidebar.write(f"{agent_name}: {len(history)} ciclos")

st.sidebar.subheader("🔧 Configuração")
st.sidebar.write("Modo: Simulação")
st.sidebar.write("Diretório ASL: `./src/asl/`")

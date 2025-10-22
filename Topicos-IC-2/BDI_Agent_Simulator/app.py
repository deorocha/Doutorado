import streamlit as st
import os
import re
import time
import datetime
import glob
import random
from queue import Queue, Empty
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
ASL_PATH = PROJECT_ROOT / "src/asl"

# Função para carregar CSS externo
def load_external_css(css_file_path):
    try:
        with open(css_file_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo CSS não encontrado: {css_file_path}")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {str(e)}")

# Carregar CSS externo
load_external_css(CSS_PATH)

# Configuração da página para layout wide
st.set_page_config(
    page_title="Simulador MAS2J",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
if 'environment' not in st.session_state:
    st.session_state.environment = {}

# Fila para comunicação
log_queue = Queue()
message_queue = Queue()

def log_message(agent_name, message):
    """Adiciona mensagem à fila de logs"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_queue.put(f"[{timestamp}] {agent_name}: {message}")

def send_message(sender, receiver, message):
    """Envia mensagem entre agentes"""
    message_queue.put({
        'sender': sender,
        'receiver': receiver,
        'message': message,
        'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
    })
    log_message("Comunicação", f"{sender} -> {receiver}: {message}")

def add_agent_history(agent_name, cycle, beliefs, goals, actions):
    """Adiciona um registro ao histórico do agente"""
    if agent_name not in st.session_state.agents_history:
        st.session_state.agents_history[agent_name] = []
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.agents_history[agent_name].append({
        'time': timestamp,
        'cycle': cycle,
        'beliefs': beliefs,
        'goals': goals,
        'actions': actions
    })
    
    # Manter apenas os últimos 50 registros por agente
    if len(st.session_state.agents_history[agent_name]) > 50:
        st.session_state.agents_history[agent_name].pop(0)

class Environment:
    """Simula o ambiente dos agentes"""
    
    def __init__(self):
        self.grid_size = (6, 6)
        self.litter_positions = [(1, 1), (2, 2), (3, 3), (4, 4)]
        self.coin_position = (2, 3)
        self.incinerator_position = (3, 3)
        self.visited_positions = set()
        
    def get_perception(self, agent_position):
        """Retorna as percepções do ambiente para um agente"""
        perceptions = []
        x, y = agent_position
        
        # Verifica se há lixo na posição atual
        if agent_position in self.litter_positions:
            perceptions.append("lixo_na_posicao")
            perceptions.append(f"lixo_pos({x},{y})")
        
        # Verifica se há moeda na posição atual
        if agent_position == self.coin_position:
            perceptions.append("moeda_na_posicao")
        
        # Verifica posições adjacentes
        for dx, dy in [(0,1), (1,0), (0,-1), (-1,0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.grid_size[0] and 0 <= ny < self.grid_size[1]:
                if (nx, ny) in self.litter_positions:
                    perceptions.append(f"lixo_proximo({nx},{ny})")
        
        return perceptions
    
    def remove_litter(self, position):
        """Remove lixo do ambiente"""
        if position in self.litter_positions:
            self.litter_positions.remove(position)
            return True
        return False
    
    def remove_coin(self, position):
        """Remove moeda do ambiente"""
        if position == self.coin_position:
            self.coin_position = None
            return True
        return False
    
    def mark_visited(self, position):
        """Marca posição como visitada"""
        self.visited_positions.add(position)

class ASLInterpreter:
    """Interpreta e executa código ASL"""
    
    def __init__(self, agent_name, asl_code, environment):
        self.agent_name = agent_name
        self.asl_code = asl_code
        self.environment = environment
        self.beliefs = set()
        self.goals = set()
        self.plans = []
        self.position = (0, 0) if agent_name == "r1" else (3, 3)
        self.loaded = False
        self.current_plan = None
        self.plan_step = 0
        
    def load_initial_state(self):
        """Carrega o estado inicial do agente a partir do código ASL"""
        try:
            lines = self.asl_code.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Carrega crenças iniciais
                if line.endswith('.'):
                    belief = line[:-1].strip()
                    if belief.startswith('pos(') or belief.startswith('r2_pos('):
                        self.beliefs.add(belief)
                
                # Carrega metas iniciais
                if line.startswith('!') and '.' in line:
                    goal = line.split('.')[0].strip()
                    self.goals.add(goal)
            
            # Carrega planos
            self._parse_plans()
            self.loaded = True
            log_message(self.agent_name, f"Estado inicial carregado: {len(self.beliefs)} crenças, {len(self.goals)} metas, {len(self.plans)} planos")
            
        except Exception as e:
            log_message("Erro", f"Erro ao carregar agente {self.agent_name}: {str(e)}")
    
    def _parse_plans(self):
        """Analisa os planos do código ASL"""
        lines = self.asl_code.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('+!'):
                # Encontrou um plano
                trigger = line.split('<-')[0].strip()
                context = None
                body = []
                
                # Verifica se tem contexto
                if ':' in trigger:
                    parts = trigger.split(':', 1)
                    trigger = parts[0].strip()
                    context = parts[1].strip()
                
                # Lê o corpo do plano
                i += 1
                while i < len(lines) and lines[i].strip().startswith('    '):
                    body_line = lines[i].strip()
                    if body_line and not body_line.startswith('//'):
                        body.append(body_line)
                    i += 1
                
                self.plans.append({
                    'trigger': trigger,
                    'context': context,
                    'body': body
                })
            else:
                i += 1
    
    def perceive_environment(self):
        """Atualiza crenças baseadas na percepção do ambiente"""
        perceptions = self.environment.get_perception(self.position)
        
        for perception in perceptions:
            if perception not in self.beliefs:
                self.beliefs.add(perception)
                log_message(self.agent_name, f"Nova percepção: {perception}")
        
        # Atualiza posição atual
        pos_belief = f"pos({self.position[0]},{self.position[1]})"
        old_pos = [b for b in self.beliefs if b.startswith('pos(')]
        for op in old_pos:
            self.beliefs.remove(op)
        self.beliefs.add(pos_belief)
        
        # Marca como visitado
        self.environment.mark_visited(self.position)
    
    def check_context(self, context):
        """Verifica se o contexto de um plano é satisfeito"""
        if not context:
            return True
        
        # Lógica simples para verificar contexto
        conditions = context.split('&')
        for condition in conditions:
            condition = condition.strip()
            negated = False
            
            if condition.startswith('not '):
                condition = condition[4:].strip()
                negated = True
            
            if negated:
                if condition in self.beliefs:
                    return False
            else:
                if condition not in self.beliefs:
                    return False
        
        return True
    
    def execute_action(self, action):
        """Executa uma ação do plano"""
        action = action.strip()
        
        try:
            if action.startswith('.print('):
                message = action[7:-1]
                log_message(self.agent_name, message)
                return True
                
            elif action.startswith('!'):
                goal = action
                self.goals.add(goal)
                log_message(self.agent_name, f"Adicionando meta: {goal}")
                return True
                
            elif action.startswith('+'):
                belief = action[1:]
                self.beliefs.add(belief)
                log_message(self.agent_name, f"Adicionando crença: {belief}")
                return True
                
            elif action.startswith('-'):
                belief = action[1:]
                if belief in self.beliefs:
                    self.beliefs.remove(belief)
                    log_message(self.agent_name, f"Removendo crença: {belief}")
                return True
                
            elif action == 'pick_lixo':
                if self.environment.remove_litter(self.position):
                    litter_belief = f"lixo_coletado({self.position[0]},{self.position[1]})"
                    self.beliefs.add(litter_belief)
                    log_message(self.agent_name, "Lixo coletado com sucesso!")
                    return True
                else:
                    log_message(self.agent_name, "Erro: Não há lixo para coletar aqui")
                    return False
                    
            elif action == 'drop_lixo':
                send_message(self.agent_name, "r2", "lixo_para_incinerar")
                log_message(self.agent_name, "Lixo entregue ao R2")
                return True
                
            elif action == 'pick_moeda':
                if self.environment.remove_coin(self.position):
                    self.beliefs.add("moeda_coletada")
                    log_message(self.agent_name, "Moeda coletada com sucesso!")
                    return True
                else:
                    log_message(self.agent_name, "Erro: Não há moeda para coletar aqui")
                    return False
                    
            elif action == 'incinerate':
                log_message(self.agent_name, "Incinerando lixo...")
                time.sleep(1)
                log_message(self.agent_name, "Lixo incinerado com sucesso!")
                return True
                
            elif action.startswith('calculate_path'):
                # Simula cálculo de caminho
                log_message(self.agent_name, "Calculando melhor caminho...")
                self.beliefs.add("caminho_disponivel")
                self.beliefs.add("caminho_tamanho(5)")
                return True
                
            elif action == 'follow_path':
                # Move o agente em uma direção aleatória
                directions = [(0,1), (1,0), (0,-1), (-1,0)]
                dx, dy = random.choice(directions)
                new_x = max(0, min(5, self.position[0] + dx))
                new_y = max(0, min(5, self.position[1] + dy))
                self.position = (new_x, new_y)
                log_message(self.agent_name, f"Movendo para posição ({new_x},{new_y})")
                return True
                
            elif action.startswith('move('):
                # Move em direção específica
                direction = action[5:-1]
                moves = {
                    'up': (-1, 0), 'down': (1, 0),
                    'left': (0, -1), 'right': (0, 1)
                }
                if direction in moves:
                    dx, dy = moves[direction]
                    new_x = max(0, min(5, self.position[0] + dx))
                    new_y = max(0, min(5, self.position[1] + dy))
                    self.position = (new_x, new_y)
                    log_message(self.agent_name, f"Movendo {direction} para ({new_x},{new_y})")
                    return True
                
            elif '.findall' in action or '.random' in action:
                # Simula funções built-in
                log_message(self.agent_name, f"Executando função: {action}")
                return True
                
            elif '.wait' in action:
                # Simula espera
                wait_time = int(re.findall(r'\d+', action)[0])
                time.sleep(wait_time / 1000)
                return True
                
            else:
                log_message(self.agent_name, f"Ação executada: {action}")
                return True
                
        except Exception as e:
            log_message("Erro", f"Erro na ação {action}: {str(e)}")
            return False
    
    def execute_cycle(self):
        """Executa um ciclo de raciocínio do agente"""
        if not self.loaded:
            return None
        
        # Processa mensagens recebidas
        self._process_messages()
        
        # Percepção do ambiente
        self.perceive_environment()
        
        # Verifica metas ativas
        active_goals = list(self.goals)
        
        # Tenta executar planos para cada meta
        executed = False
        actions_executed = []
        
        for goal in active_goals:
            if executed:
                break
                
            for plan in self.plans:
                trigger_goal = plan['trigger'][2:]  # Remove '+!'
                
                if trigger_goal == goal and self.check_context(plan['context']):
                    log_message(self.agent_name, f"Executando plano para: {goal}")
                    
                    # Executa o corpo do plano
                    for action in plan['body']:
                        success = self.execute_action(action)
                        actions_executed.append(action)
                        
                        if not success:
                            log_message(self.agent_name, f"Falha na ação: {action}")
                            break
                    
                    executed = True
                    self.goals.discard(goal)
                    break
        
        # Se não executou nenhum plano específico, tenta planos sem contexto
        if not executed:
            for plan in self.plans:
                if plan['trigger'].startswith('+!') and not plan['context']:
                    goal = plan['trigger'][2:]
                    if goal not in self.goals:
                        continue
                        
                    log_message(self.agent_name, f"Executando plano padrão para: {goal}")
                    
                    for action in plan['body']:
                        success = self.execute_action(action)
                        actions_executed.append(action)
                        
                        if not success:
                            break
                    
                    self.goals.discard(goal)
                    executed = True
                    break
        
        # Verifica se todos os lixos foram coletados
        litter_beliefs = [b for b in self.beliefs if b.startswith('lixo_coletado')]
        if len(litter_beliefs) >= 4 and "todos_lixos_coletados" not in self.beliefs:
            self.beliefs.add("todos_lixos_coletados")
            log_message(self.agent_name, "Todos os lixos foram coletados!")
        
        return {
            'crencas': ", ".join(sorted(self.beliefs)),
            'metas': ", ".join(sorted(self.goals)),
            'acoes': ", ".join(actions_executed) if actions_executed else "Nenhuma",
            'posicao': self.position
        }
    
    def _process_messages(self):
        """Processa mensagens recebidas"""
        temp_queue = Queue()
        
        try:
            while True:
                msg = message_queue.get_nowait()
                if msg['receiver'] == self.agent_name:
                    # Processa a mensagem
                    if msg['message'] == "lixo_para_incinerar":
                        self.beliefs.add("lixo_para_incinerar")
                        log_message(self.agent_name, "Recebido lixo do R1 - incinerando")
                        self.execute_action("incinerate")
                else:
                    temp_queue.put(msg)
        except Empty:
            pass
        
        # Retorna mensagens não processadas para a fila
        while not temp_queue.empty():
            message_queue.put(temp_queue.get())

def initialize_simulation(mas2j_content):
    """Inicializa a simulação baseada no arquivo MAS2J"""
    try:
        # Extrair agentes do arquivo mas2j
        agentes = re.findall(r'agents:\s*((?:\s*\w+;)+)', mas2j_content)
        if not agentes:
            log_message("Sistema", "Nenhum agente encontrado no arquivo")
            return False
        
        nomes_agentes = re.findall(r'(\w+);', agentes[0])
        log_message("Sistema", f"Inicializando simulação para {len(nomes_agentes)} agentes")
        
        # Criar ambiente
        st.session_state.environment = Environment()
        
        # Criar interpretadores para cada agente
        st.session_state.simulators = {}
        st.session_state.agents_history = {}
        
        for nome in nomes_agentes:
            asl_path = ASL_PATH / f"{nome}.asl"
            if os.path.exists(asl_path):
                try:
                    with open(asl_path, 'r', encoding='utf-8') as f:
                        asl_content = f.read()
                    
                    interpreter = ASLInterpreter(nome, asl_content, st.session_state.environment)
                    interpreter.load_initial_state()
                    
                    st.session_state.simulators[nome] = interpreter
                    st.session_state.agents_state[nome] = {
                        'crencas': "Carregando...",
                        'metas': "Carregando...",
                        'acoes': "Nenhuma",
                        'posicao': interpreter.position
                    }
                    
                    # Inicializar histórico
                    st.session_state.agents_history[nome] = []
                    log_message("Sistema", f"Interpretador criado para agente {nome}")
                    
                except Exception as e:
                    log_message("Sistema", f"Erro ao carregar agente {nome}: {str(e)}")
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
    """Executa um ciclo da simulação para todos os agentes"""
    if not st.session_state.simulators:
        return False
    
    current_time = time.time()
    
    # Executar ciclo para cada agente
    for nome, interpreter in st.session_state.simulators.items():
        state = interpreter.execute_cycle()
        if state:
            st.session_state.agents_state[nome] = {
                'crencas': state['crencas'],
                'metas': state['metas'],
                'acoes': state['acoes'],
                'posicao': state['posicao']
            }
            
            add_agent_history(
                nome, 
                getattr(interpreter, 'cycle_count', 0),
                state['crencas'],
                state['metas'],
                state['acoes']
            )
            
            # Incrementa contador de ciclos
            if not hasattr(interpreter, 'cycle_count'):
                interpreter.cycle_count = 1
            else:
                interpreter.cycle_count += 1
    
    # Verificar condições de término
    all_completed = all(
        "moeda_coletada" in interpreter.beliefs and 
        "todos_lixos_coletados" in interpreter.beliefs
        for interpreter in st.session_state.simulators.values()
        if interpreter.agent_name == "r1"
    )
    
    if all_completed:
        log_message("Sistema", "Missão concluída com sucesso! Todos os lixos coletados e moeda encontrada.")
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
    st.session_state.environment = {}
    
    if initialize_simulation(mas2j_content):
        log_message("Sistema", "Simulação iniciada - executando agentes baseados nos arquivos ASL")
    else:
        st.session_state.simulation_running = False
        log_message("Sistema", "Falha ao iniciar simulação")

def stop_simulation():
    """Para a simulação"""
    st.session_state.simulation_running = False
    st.session_state.simulation_started = False
    log_message("Sistema", "Simulação parada")

def format_history_line(time_str, cycle, beliefs, goals, actions):
    """Formata uma linha do histórico com alinhamento fixo"""
    # Definir larguras das colunas
    time_width = 10
    cycle_width = 6
    beliefs_width = 40
    goals_width = 30
    actions_width = 40
    
    # Formatar cada campo com a largura fixa
    time_formatted = time_str.ljust(time_width)
    cycle_formatted = str(cycle).ljust(cycle_width)
    beliefs_formatted = (beliefs[:beliefs_width-3] + '...') if len(beliefs) > beliefs_width else beliefs.ljust(beliefs_width)
    goals_formatted = (goals[:goals_width-3] + '...') if len(goals) > goals_width else goals.ljust(goals_width)
    actions_formatted = (actions[:actions_width-3] + '...') if len(actions) > actions_width else actions.ljust(actions_width)
    
    return f"{time_formatted} {cycle_formatted} {beliefs_formatted} {goals_formatted} {actions_formatted}"

def render_agent_history(agent_name):
    """Renderiza o histórico de um agente em formato de log alinhado"""
    if agent_name not in st.session_state.agents_history:
        st.info(f"Nenhum histórico disponível para {agent_name}")
        return
    
    history = st.session_state.agents_history[agent_name]
    
    # Criar cabeçalho
    header = format_history_line("Time", "Ciclo", "Crenças", "Metas", "Ações")
    separator = "-" * len(header)
    
    # Criar linhas do histórico
    history_lines = [header, separator]
    for record in reversed(history):  # Mais recente primeiro
        line = format_history_line(
            record['time'], 
            record['cycle'], 
            record['beliefs'], 
            record['goals'],
            record['actions']
        )
        history_lines.append(line)
    
    # Juntar todas as linhas
    history_text = "\n".join(history_lines)
    
    # Exibir em um bloco de texto com formatação
    st.markdown(f'<div class="agent-history">{history_text}</div>', unsafe_allow_html=True)

# Interface principal
st.title("🤖 Simulador de Sistemas Multiagentes - Interpretador ASL")

# Buscar arquivos .mas2j no diretório atual
st.subheader("📁 Seletor de Arquivo MAS2J")

# Listar arquivos .mas2j disponíveis
mas2j_files = glob.glob("*.mas2j") + glob.glob("**/*.mas2j", recursive=True)

mas2j_content = None
if mas2j_files:
    selected_file = st.selectbox(
        "Selecione o arquivo .mas2j:",
        mas2j_files,
        index=0
    )
    
    try:
        with open(selected_file, 'r', encoding='utf-8') as f:
            mas2j_content = f.read()
        st.success(f"✅ Arquivo {selected_file} carregado com sucesso!")
        
        # Mostrar agentes detectados
        agentes = re.findall(r'agents:\s*((?:\s*\w+;)+)', mas2j_content)
        if agentes:
            nomes = re.findall(r'(\w+);', agentes[0])
            st.success(f"✅ {len(nomes)} agentes detectados: {', '.join(nomes)}")
            
            # Mostrar conteúdo dos arquivos ASL
            for nome in nomes:
                with st.expander(f"Agente: {nome}", expanded=False):
                    try:
                        asl_path = ASL_PATH / f"{nome}.asl"
                        if os.path.exists(asl_path):
                            with open(asl_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                st.code(content, language='prolog')
                        else:
                            st.error(f"Arquivo {asl_path} não encontrado")
                    except Exception as e:
                        st.error(f"Erro ao ler arquivo ASL: {str(e)}")
        
    except Exception as e:
        st.error(f"Erro ao ler o arquivo {selected_file}: {str(e)}")
        mas2j_content = None
else:
    st.warning("⚠️ Nenhum arquivo .mas2j encontrado no diretório do projeto.")
    
    # Fallback: ainda permite upload manual
    arquivo = st.file_uploader("Ou faça upload manual de um arquivo .mas2j", type=['mas2j'])
    if arquivo:
        mas2j_content = arquivo.read().decode('utf-8')
        
        # Mostrar agentes detectados (para upload manual)
        agentes = re.findall(r'agents:\s*((?:\s*\w+;)+)', mas2j_content)
        if agentes:
            nomes = re.findall(r'(\w+);', agentes[0])
            st.success(f"✅ {len(nomes)} agentes detectados: {', '.join(nomes)}")
            
            # Mostrar conteúdo dos arquivos ASL
            for nome in nomes:
                with st.expander(f"Agente: {nome}", expanded=False):
                    try:
                        asl_path = ASL_PATH / f"{nome}.asl"
                        if os.path.exists(asl_path):
                            with open(asl_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                st.code(content, language='prolog')
                        else:
                            st.error(f"Arquivo {asl_path} não encontrado")
                    except Exception as e:
                        st.error(f"Erro ao ler arquivo ASL: {str(e)}")

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
    time.sleep(2)  # Intervalo entre ciclos
    st.rerun()

# Mostrar logs em tempo real
st.subheader("📋 Logs de Execução")
if st.session_state.logs:
    logs_text = "\n".join(st.session_state.logs[-20:])  # Mostrar apenas os últimos 20 logs
    st.markdown(f'<div class="log-container">{logs_text}</div>', unsafe_allow_html=True)
else:
    st.info("Nenhum log disponível. Execute a simulação para ver os logs.")

# Mostrar estado atual dos agentes
st.subheader("🔍 Estado Atual dos Agentes")
if st.session_state.agents_state:
    for agent_name, state in st.session_state.agents_state.items():
        with st.expander(f"Agente {agent_name} - Posição: {state.get('posicao', 'N/A')}", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write("**Crenças:**")
                st.text_area("", state['crencas'], height=100, key=f"beliefs_{agent_name}", label_visibility="collapsed")
            with col2:
                st.write("**Metas:**")
                st.text_area("", state['metas'], height=100, key=f"goals_{agent_name}", label_visibility="collapsed")
            with col3:
                st.write("**Ações Executadas:**")
                st.text_area("", state['acoes'], height=100, key=f"actions_{agent_name}", label_visibility="collapsed")
else:
    st.info("Nenhum estado disponível. Execute a simulação para ver o estado dos agentes.")

# Mostrar histórico dos agentes
st.subheader("📊 Histórico dos Agentes")
if st.session_state.agents_history:
    for agent_name in st.session_state.agents_history.keys():
        with st.expander(f"Histórico do Agente {agent_name}", expanded=False):
            render_agent_history(agent_name)
else:
    st.info("Nenhum histórico disponível. Execute a simulação para ver o histórico dos agentes.")

# Informações do sistema
st.sidebar.subheader("⚙️ Status do Sistema")
if st.session_state.simulation_running:
    st.sidebar.success("✅ Simulação em execução")
    if st.session_state.simulators:
        active_agents = len(st.session_state.simulators)
        st.sidebar.info(f"Agentes ativos: {active_agents}")
        
        # Mostrar estado do ambiente
        if st.session_state.environment:
            env = st.session_state.environment
            st.sidebar.info(f"Lixos restantes: {len(env.litter_positions)}")
            st.sidebar.info(f"Moeda coletada: {env.coin_position is None}")
else:
    st.sidebar.info("⏸️ Simulação parada")

# Debug information
st.sidebar.subheader("🔍 Debug")
st.sidebar.write(f"Arquivos .mas2j encontrados: {len(mas2j_files)}")

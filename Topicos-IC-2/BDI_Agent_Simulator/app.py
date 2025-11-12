import streamlit as st
import re
import os
from pathlib import Path
import time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).parent

# Configuração da página
st.set_page_config(page_title="Simulador MAS2J", layout="wide")
st.title("🔍 Analisador de Projetos MAS2J")

def clear_simulation_state():
    """Limpa o estado da simulação quando um novo projeto é selecionado"""
    keys_to_clear = ['run_simulation', 'agent_history', 'agent_messages', 'current_project']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def get_project_folders():
    """Obtém a lista de pastas de projetos dentro da pasta projects"""
    project_dir = PROJECT_ROOT / "projects"
    if not project_dir.exists():
        return []
    project_folders = [f for f in project_dir.iterdir() if f.is_dir()]
    projects = []
    for folder in project_folders:
        mas_files = list(folder.glob("*.mas2j")) + list(folder.glob("*.mas3j"))
        if mas_files:
            main_file = mas_files[0]
            projects.append({
                'name': folder.name,
                'folder': folder,
                'main_file': main_file,
                'all_files': mas_files
            })
    return projects

def load_project_file(project_info):
    """Carrega o conteúdo do arquivo principal de um projeto"""
    if isinstance(project_info, dict) and 'main_file' in project_info:
        project_path = project_info['main_file']
    else:
        project_path = PROJECT_ROOT / "projects" / project_info
    if project_path.exists():
        try:
            with open(project_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            with open(project_path, 'r', encoding='latin-1') as file:
                return file.read()
    else:
        st.error(f"Arquivo não encontrado: {project_path}")
    return None

def parse_project_paths(file_content):
    """Extrai os caminhos do projeto do conteúdo do arquivo .mas2j"""
    content_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', file_content, flags=re.MULTILINE | re.DOTALL)
    paths = {}
    asl_pattern = r'aslSourcePath\s*:\s*"([^"]+)"'
    asl_match = re.search(asl_pattern, content_no_comments)
    if asl_match:
        paths['asl_source_path'] = asl_match.group(1)
    class_pattern = r'classPath\s*:\s*"([^"]+)"'
    class_match = re.search(class_pattern, content_no_comments)
    if class_match:
        paths['class_path'] = class_match.group(1)
    return paths

def get_all_project_files(project_info, project_content=None):
    """Obtém todos os arquivos do projeto, incluindo aslSourcePath e classPath"""
    if isinstance(project_info, dict) and 'folder' in project_info:
        folder = project_info['folder']
        all_files = []
        root_files = [f for f in folder.iterdir() if f.is_file()]
        all_files.extend([f for f in root_files if f.suffix.lower() not in ['.mas2j', '.mas3j']])
        if project_content:
            paths = parse_project_paths(project_content)
            if 'asl_source_path' in paths:
                asl_path = folder / paths['asl_source_path']
                if asl_path.exists() and asl_path.is_dir():
                    asl_files = list(asl_path.rglob("*"))
                    all_files.extend([f for f in asl_files if f.is_file()])
            if 'class_path' in paths:
                class_path = folder / paths['class_path']
                if class_path.exists() and class_path.is_dir():
                    class_files = list(class_path.rglob("*"))
                    all_files.extend([f for f in class_files if f.is_file()])
        seen_files = set()
        unique_files = []
        for file in all_files:
            if file.name not in seen_files:
                seen_files.add(file.name)
                unique_files.append(file)
        return unique_files
    return []

def parse_mas2j(file_content):
    """Extrai agentes do .mas2j – inclui formato agentArchClass"""
    import re
    content = re.sub(r'//.*?$|/\*.*?\*/', '', file_content, flags=re.MULTILINE | re.DOTALL)
    raw = re.findall(r'^\s*(\w+)\s+agentArchClass\s+\w+\s*;', content, re.MULTILINE)
    block = re.search(r'agents\s*:\s*\{([^}]+)\}', content, re.DOTALL)
    if block:
        raw += re.findall(r'(\w+)(?=\s*[,;})])', block.group(1))
    keywords = {'infrastructure', 'environment', 'aslSourcePath', 'classPath',
                'initialisation', 'launchParameters', 'agents', 'agent'}
    agents = [a for a in raw if a.lower() not in keywords and len(a) > 1]
    return list(set(agents))

def parse_asl_files(project_info, project_content=None):
    """Extrai apenas nomes de agentes dos arquivos .asl – ignora goals/planos"""
    asl_agents = []
    all_files = get_all_project_files(project_info, project_content)
    asl_files = [f for f in all_files if f.suffix.lower() == '.asl']
    for asl_file in asl_files:
        try:
            with open(asl_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(asl_file, 'r', encoding='latin-1') as f:
                content = f.read()
        content = re.sub(r'//.*?$|/\*.*?\*/', '', content, flags=re.MULTILINE | re.DOTALL)
        agent_name = asl_file.stem
        if agent_name and agent_name not in ['environment', 'utils', 'common']:
            asl_agents.append(agent_name)
        includes = re.findall(r'include\s*"([^"]+)"', content)
        for inc in includes:
            if '.' not in inc or inc.endswith('.asl'):
                asl_agents.append(inc.replace('.asl', ''))
        keywords = {'true', 'false', 'not', 'and', 'or', 'if', 'then', 'else',
                    'bel', 'goal', 'test', 'plan', 'source', 'self', 'percept',
                    'action', 'internal', 'external', 'init', 'main', 'stop',
                    'print', 'send', 'broadcast', 'include'}
        asl_agents = [a for a in asl_agents if a.lower() not in keywords and len(a) > 1]
    return list(set(asl_agents))

def get_all_agents(project_info, project_content):
    """Combina agentes do arquivo .mas2j e dos arquivos .asl"""
    mas2j_agents = parse_mas2j(project_content)
    asl_agents = parse_asl_files(project_info, project_content)
    all_agents = list(set(mas2j_agents + asl_agents))
    all_agents.sort()
    return all_agents

def simulate_communication(agents):
    """Simula a comunicação entre agentes e retorna logs, histórico e mensagens"""
    logs = []
    agent_history = {agent: [] for agent in agents}
    agent_messages = []
    if not agents:
        logs.append("⚠️ Nenhum agente encontrado para simular comunicação")
        return logs, agent_history, agent_messages
    start_time = datetime.now()
    logs.append("🚀 Iniciando sistema multiagente...")
    for agent in agents:
        logs.append(f"✅ {agent} inicializado")
        current_time = datetime.now()
        elapsed = current_time - start_time
        milliseconds = int(elapsed.total_seconds() * 1000)
        timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
        agent_messages.append({'Hora': timestamp, 'Agente': agent, 'Mensagem': f"[INIT] Agente {agent} inicializado com sucesso"})
        agent_history[agent].append({'Hora': timestamp, 'Ciclo': 0, 'Crenças': "sistema_iniciado, pronto_para_comunicar", 'Metas': "inicializar_sistema"})
    logs.append("---")
    logs.append("📨 Iniciando comunicação entre agentes...")
    for cycle, sender in enumerate(agents, 1):
        receiver = agents[(cycle) % len(agents)]
        current_time = datetime.now()
        elapsed = current_time - start_time
        milliseconds = int(elapsed.total_seconds() * 1000)
        timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
        agent_messages.append({'Hora': timestamp, 'Agente': sender, 'Mensagem': f"[SEND] Enviando mensagem para {receiver}: 'Olá {receiver}!'"})
        agent_history[sender].append({'Hora': timestamp, 'Ciclo': cycle, 'Crenças': f"enviando_msg_para_{receiver}, comunicacao_ativa", 'Metas': f"enviar_mensagem_{receiver}, manter_conexao"})
        logs.append(f"📤 {sender} → {receiver}: Mensagem de saudação")
        time.sleep(0.1)
        agent_messages.append({'Hora': timestamp, 'Agente': receiver, 'Mensagem': f"[RECV] Mensagem recebida de {sender}: 'Olá {receiver}!'"})
        agent_messages.append({'Hora': timestamp, 'Agente': receiver, 'Mensagem': f"[SEND] Respondendo para {sender}: 'Olá {sender}! Recebida sua mensagem.'"})
        agent_history[receiver].append({'Hora': timestamp, 'Ciclo': cycle, 'Crenças': f"recebendo_msg_de_{sender}, mensagem_processada", 'Metas': f"responder_{sender}, processar_mensagem"})
        logs.append(f"📥 {receiver} ← {sender}: Confirmação recebida")
        time.sleep(0.1)
        agent_messages.append({'Hora': timestamp, 'Agente': sender, 'Mensagem': f"[RECV] Confirmação recebida de {receiver}"})
        if cycle == 1:
            logs.append(f"📢 {sender} faz broadcast para todos os agentes")
            agent_messages.append({'Hora': timestamp, 'Agente': sender, 'Mensagem': f"[BROADCAST] Enviando mensagem para todos os agentes: 'Sincronização iniciada'"})
            agent_history[sender].append({'Hora': timestamp, 'Ciclo': cycle, 'Crenças': "broadcast_enviado, todos_notificados", 'Metas': "coordenar_agentes, manter_sincronizacao"})
            for other_agent in agents:
                if other_agent != sender:
                    agent_messages.append({'Hora': timestamp, 'Agente': other_agent, 'Mensagem': f"[RECV] Broadcast recebido de {sender}: 'Sincronização iniciada'"})
    final_cycle = len(agents) + 1
    current_time = datetime.now()
    elapsed = current_time - start_time
    milliseconds = int(elapsed.total_seconds() * 1000)
    timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
    for agent in agents:
        agent_messages.append({'Hora': timestamp, 'Agente': agent, 'Mensagem': f"[INFO] Finalizando execução - todas as tarefas concluídas"})
        agent_history[agent].append({'Hora': timestamp, 'Ciclo': final_cycle, 'Crenças': "sistema_finalizado, todas_tarefas_concluidas", 'Metas': "finalizar_processos, aguardar_nova_execucao"})
    logs.append("---")
    logs.append("✅ Todos os agentes finalizaram suas tarefas")
    return logs, agent_history, agent_messages

def create_agent_history_table(agent_history, agent_name):
    """Cria uma tabela DataFrame para o histórico de um agente"""
    if agent_name not in agent_history or not agent_history[agent_name]:
        return pd.DataFrame()
    df = pd.DataFrame(agent_history[agent_name])
    return df

def create_messages_table(agent_messages):
    """Cria uma tabela DataFrame para as mensagens dos agentes"""
    if not agent_messages:
        return pd.DataFrame()
    df = pd.DataFrame(agent_messages)
    return df

def get_file_language(file_path):
    """Determina a linguagem para syntax highlighting baseada na extensão do arquivo"""
    extension = file_path.suffix.lower()
    language_map = {
        '.asl': 'lisp', '.java': 'java', '.py': 'python', '.xml': 'xml',
        '.json': 'json', '.txt': 'text', '.md': 'markdown', '.yml': 'yaml',
        '.yaml': 'yaml', '.properties': 'properties', '.sh': 'bash',
        '.bat': 'bat', '.sql': 'sql', '.html': 'html', '.css': 'css',
        '.js': 'javascript'
    }
    return language_map.get(extension, 'text')

def create_communication_diagram(agent_messages, agents):
    """Cria um diagrama de comunicação entre agentes que mostra TODAS as comunicações"""
    
    if not agent_messages:
        return None
    
    # Filtra apenas mensagens de comunicação relevantes
    comm_messages = [
        msg for msg in agent_messages 
        if any(tag in msg['Mensagem'] for tag in ['[SEND]', '[RECV]', '[BROADCAST]', '[INFORM]', '[REQUEST]'])
    ]
    
    if not comm_messages:
        return None
    
    # Cria a figura do diagrama
    fig = go.Figure()
    
    # Posições dos agentes no eixo X
    agent_positions = {agent: i for i, agent in enumerate(agents)}
    
    # Espaçamento vertical mais consistente
    vertical_spacing = 8.0
    max_height = max(len(comm_messages) * vertical_spacing, 25)
    
    # Adiciona linhas verticais para cada agente
    for agent, x_pos in agent_positions.items():
        fig.add_shape(
            type="line",
            x0=x_pos, y0=0, x1=x_pos, y1=max_height,
            line=dict(color="lightgray", width=3)
        )
    
    # Processa TODAS as mensagens para criar comunicações
    communications = []
    # Conjunto para evitar comunicações duplicadas
    seen_communications = set()
    
    # Contadores separados para diferentes tipos de comunicação
    broadcast_count = 0
    point_to_point_count = 0
    
    for i, msg in enumerate(comm_messages):
        message_text = msg['Mensagem']
        agent = msg['Agente']
        
        # Posição Y baseada no índice da mensagem com espaçamento consistente
        y_pos = i * vertical_spacing + 2
        
        # Extrai informações da mensagem
        if '[SEND]' in message_text:
            if 'para' in message_text:
                match = re.search(r'para (\w+):', message_text)
                if match:
                    target_agent = match.group(1)
                    if target_agent in agents:
                        # Cria uma chave única para identificar comunicação duplicada
                        comm_key = (agent, target_agent, 'SEND', message_text)
                        if comm_key not in seen_communications:
                            communications.append({
                                'from': agent,
                                'to': target_agent,
                                'message': message_text,
                                'time': msg['Hora'],
                                'type': 'SEND',
                                'y_pos': y_pos,
                                'index': point_to_point_count
                            })
                            seen_communications.add(comm_key)
                            point_to_point_count += 1
        
        elif '[BROADCAST]' in message_text:
            # Para broadcast, usamos uma única comunicação com 'ALL'
            comm_key = (agent, 'ALL', 'BROADCAST', message_text)
            if comm_key not in seen_communications:
                communications.append({
                    'from': agent,
                    'to': 'ALL',
                    'message': message_text,
                    'time': msg['Hora'],
                    'type': 'BROADCAST',
                    'y_pos': y_pos,
                    'index': i
                })
                seen_communications.add(comm_key)
                broadcast_count += 1
        
        elif '[RECV]' in message_text:
            if 'de' in message_text:
                match = re.search(r'de (\w+):', message_text)
                if match:
                    source_agent = match.group(1)
                    if source_agent in agents:
                        comm_key = (source_agent, agent, 'RECV', message_text)
                        if comm_key not in seen_communications:
                            communications.append({
                                'from': source_agent,
                                'to': agent,
                                'message': message_text,
                                'time': msg['Hora'],
                                'type': 'RECV',
                                'y_pos': y_pos,
                                'index': point_to_point_count
                            })
                            seen_communications.add(comm_key)
                            point_to_point_count += 1
            else:
                # Se não conseguiu extrair o remetente, cria uma comunicação genérica
                comm_key = ('UNKNOWN', agent, 'RECV', message_text)
                if comm_key not in seen_communications:
                    communications.append({
                        'from': 'UNKNOWN',
                        'to': agent,
                        'message': message_text,
                        'time': msg['Hora'],
                        'type': 'RECV',
                        'y_pos': y_pos,
                        'index': point_to_point_count
                    })
                    seen_communications.add(comm_key)
                    point_to_point_count += 1
        
        elif '[INFORM]' in message_text:
            # Para INFORM, tratamos como broadcast
            comm_key = (agent, 'ALL', 'INFORM', message_text)
            if comm_key not in seen_communications:
                communications.append({
                    'from': agent,
                    'to': 'ALL',
                    'message': message_text,
                    'time': msg['Hora'],
                    'type': 'INFORM',
                    'y_pos': y_pos,
                    'index': i
                })
                seen_communications.add(comm_key)
                broadcast_count += 1
        
        elif '[REQUEST]' in message_text:
            if 'para' in message_text:
                match = re.search(r'para (\w+):', message_text)
                if match:
                    target_agent = match.group(1)
                    if target_agent in agents:
                        comm_key = (agent, target_agent, 'REQUEST', message_text)
                        if comm_key not in seen_communications:
                            communications.append({
                                'from': agent,
                                'to': target_agent,
                                'message': message_text,
                                'time': msg['Hora'],
                                'type': 'REQUEST',
                                'y_pos': y_pos,
                                'index': point_to_point_count
                            })
                            seen_communications.add(comm_key)
                            point_to_point_count += 1
    
    # Ordena comunicações pela posição Y para melhor organização
    communications.sort(key=lambda x: x['y_pos'])
    
    # Cores para diferentes tipos de mensagens
    arrow_colors = {
        'SEND': 'blue',
        'RECV': 'green', 
        'BROADCAST': 'orange',
        'INFORM': 'purple',
        'REQUEST': 'red'
    }
    
    # Adiciona setas para cada comunicação
    for comm in communications:
        y_pos = comm['y_pos']
        
        # Verifica se os agentes existem antes de adicionar setas
        if comm['from'] not in agent_positions and comm['from'] != 'UNKNOWN':
            continue
        if comm['to'] != 'ALL' and comm['to'] not in agent_positions:
            continue
        
        if comm['to'] == 'ALL':
            for target_agent in agents:
                if target_agent != comm['from'] and target_agent in agent_positions:
                    fig.add_annotation(
                        x=agent_positions[target_agent],
                        y=y_pos,
                        ax=agent_positions.get(comm['from'], 0),
                        ay=y_pos,
                        xref="x",
                        yref="y",
                        axref="x",
                        ayref="y",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1.2,
                        arrowwidth=2.5,
                        arrowcolor=arrow_colors.get(comm['type'], 'black')
                    )
        else:
            # Para mensagens de RECV com remetente desconhecido, não desenha seta
            if comm['from'] == 'UNKNOWN':
                continue
                
            fig.add_annotation(
                x=agent_positions[comm['to']],
                y=y_pos,
                ax=agent_positions[comm['from']],
                ay=y_pos,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.2,
                arrowwidth=2.5,
                arrowcolor=arrow_colors.get(comm['type'], 'black')
            )
    
    # ---------- TEXTO DAS MENSAGENS (labels) ----------
    text_annotations = []
    seen_texts = set()

    for comm in communications:
        y_pos = comm['y_pos']
        
        message_short = comm['message'].split(':')[-1].strip().replace("'", "")[:50]
        
        # Para mensagens de RECV, ajusta o texto para ficar mais claro
        if comm['type'] == 'RECV':
            if 'de' in comm['message']:
                # Extrai apenas a parte da mensagem após "de X:"
                match = re.search(r'de \w+:\s*(.+)', comm['message'])
                if match:
                    message_short = f"Recebido: {match.group(1)}"[:50]
                else:
                    message_short = f"Recebido: {message_short}"[:50]
            else:
                message_short = f"Recebido: {message_short}"[:50]
        
        if comm['to'] == 'ALL':
            # Para BROADCAST/INFORM, adiciona apenas UMA vez o texto centralizado
            text_key = ('BROADCAST', comm['from'], message_short)
            if text_key not in seen_texts:
                # Posição Y mais consistente para broadcasts
                text_y = y_pos + 3.0  # Espaçamento fixo acima da seta
                
                text_annotations.append(dict(
                    x=len(agents) / 2 - 0.5,
                    y=text_y,
                    text=message_short,
                    showarrow=False,
                    font=dict(size=10, color="darkblue", family="Arial"),
                    opacity=1.0
                ))
                seen_texts.add(text_key)
        else:
            # Para mensagens ponto-a-ponto (SEND, RECV, REQUEST)
            text_key = (comm['from'], comm['to'], comm['type'], message_short)
            if text_key not in seen_texts:
                # Posiciona o texto com espaçamento consistente
                text_y = y_pos + 3.0  # Espaçamento fixo acima da seta
                
                # Para RECV, ajusta a posição X para ficar mais próximo do destinatário
                if comm['type'] == 'RECV':
                    x_pos = (agent_positions[comm['from']] * 0.3 + agent_positions[comm['to']] * 0.7)
                else:
                    x_pos = (agent_positions[comm['from']] + agent_positions[comm['to']]) / 2
                
                text_annotations.append(dict(
                    x=x_pos,
                    y=text_y,
                    text=message_short,
                    showarrow=False,
                    font=dict(size=10, color="darkblue", family="Arial"),
                    opacity=1.0
                ))
                seen_texts.add(text_key)
    
    # Adiciona todas as anotações de texto de uma vez (SEM CAIXAS)
    for annotation in text_annotations:
        fig.add_annotation(annotation)
    
    # Ajusta a altura máxima baseada nas comunicações
    if communications:
        max_comm_y = max(comm['y_pos'] for comm in communications)
        max_height = max(max_comm_y + 15, 25)  # Garante espaço mínimo
    
    # Adiciona retângulos para cada agente
    for agent, x_pos in agent_positions.items():
        fig.add_shape(
            type="rect",
            x0=x_pos - 0.4,
            y0=max_height + 0.5,
            x1=x_pos + 0.4,
            y1=max_height + 6.0,
            line=dict(color="darkblue", width=1),
            fillcolor="lightblue",
            opacity=0.8
        )
        
        fig.add_annotation(
            x=x_pos,
            y=max_height + 3,
            text=agent,
            showarrow=False,
            font=dict(size=10, color="black", family="Arial", weight="bold"),
            opacity=1.0
        )
    
    # Configura o layout
    fig.update_layout(
        title={
            'text': "Diagrama de Comunicação entre Agentes - Sniffer Agent",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 22, 'family': 'Arial'}
        },
        xaxis=dict(
            title="Agentes",
            tickmode='array',
            tickvals=list(agent_positions.values()),
            ticktext=[],
            showgrid=False,
            zeroline=False,
            range=[-0.5, len(agents) - 0.5]
        ),
        yaxis=dict(
            title="Tempo (Sequência de Comunicação)",
            showgrid=True,
            gridcolor="lightgray",
            zeroline=False,
            range=[-1, max_height + 6]
        ),
        showlegend=True,
        height=1500,
        width=max(1200, len(agents) * 200),
        plot_bgcolor='white',
        margin=dict(l=50, r=50, t=100, b=50)
    )
    
    # Adiciona legenda manual
    legend_elements = []
    for msg_type, color in arrow_colors.items():
        legend_elements.append(
            f"<span style='color:{color}; font-weight:bold;'>■</span> {msg_type}"
        )
    
    fig.add_annotation(
        x=0.02,
        y=0.55,
        xref="paper",
        yref="paper",
        text="<br>".join(legend_elements),
        showarrow=False,
        bgcolor="white",
        bordercolor="black",
        borderwidth=1,
        borderpad=4,
        font=dict(size=12, family="Arial"),
        xanchor="left"
    )
    
    return fig


def create_sniffer_table(agent_messages, agents):
    """Cria uma tabela estilo sniffer agent"""
    if not agent_messages:
        return None
    comm_messages = [
        msg for msg in agent_messages
        if any(tag in msg['Mensagem'] for tag in ['[SEND]', '[RECV]', '[BROADCAST]', '[REQUEST]', '[INFORM]'])
    ]
    data = []
    for i, msg in enumerate(comm_messages):
        row = {'Step': i + 1}
        message_text = msg['Mensagem']
        agent = msg['Agente']
        msg_type = "UNKNOWN"
        msg_content = message_text
        if '[SEND]' in message_text:
            msg_type = "SEND"
            if ']:' in message_text:
                msg_content = message_text.split(']:')[1].strip()
        elif '[RECV]' in message_text:
            msg_type = "RECV"
            if ']:' in message_text:
                msg_content = message_text.split(']:')[1].strip()
        elif '[BROADCAST]' in message_text:
            msg_type = "BROADCAST"
            if ']:' in message_text:
                msg_content = message_text.split(']:')[1].strip()
        elif '[REQUEST]' in message_text:
            msg_type = "REQUEST"
            if ']:' in message_text:
                msg_content = message_text.split(']:')[1].strip()
        elif '[INFORM]' in message_text:
            msg_type = "INFORM"
            if ']:' in message_text:
                msg_content = message_text.split(']:')[1].strip()
        for a in agents:
            row[a] = f"{msg_type}: {msg_content}" if a == agent else ""
        data.append(row)
    if data:
        df = pd.DataFrame(data)
        return df
    return None

# -------------------- STREAMLIT LAYOUT --------------------
projects = get_project_folders()
if projects:
    project_names = [project['name'] for project in projects]
    selected_project_name = st.sidebar.selectbox("Selecione um projeto:", project_names, index=0)
    if 'current_project' not in st.session_state:
        st.session_state.current_project = selected_project_name
    elif st.session_state.current_project != selected_project_name:
        clear_simulation_state()
        st.session_state.current_project = selected_project_name
    selected_project = next((p for p in projects if p['name'] == selected_project_name), None)
    if selected_project:
        st.subheader(f"📄 Projeto: {selected_project_name}")
        project_content = load_project_file(selected_project)
        if project_content:
            paths = parse_project_paths(project_content)
            with st.expander("📁 Estrutura do Projeto"):
                st.write(f"**Pasta:** `{selected_project['folder']}`")
                st.write(f"**Arquivo principal:** `{selected_project['main_file'].name}`")
                if 'asl_source_path' in paths:
                    st.write(f"**aslSourcePath:** `{paths['asl_source_path']}`")
                if 'class_path' in paths:
                    st.write(f"**classPath:** `{paths['class_path']}`")
                all_files = get_all_project_files(selected_project, project_content)
                if all_files:
                    st.write("**Arquivos do projeto:**")
                    for file in all_files:
                        st.write(f"- `{file.name}`")
                else:
                    st.info("Nenhum arquivo adicional encontrado")

            # NOVA ORDEM DAS ABAS: unificamos "Arquivos" e "Agentes" em "Agentes"
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 Código", "🤖 Agentes", "🔄 Simulação", "📝 Logs dos Agentes", "📊 Sniffer Agent", "🖧 Tropos Modeler"])

            # 1. Aba CÓDIGO (conteúdo do .mas2j)
            with tab1:
                st.subheader("Conteúdo do Arquivo Principal")
                st.code(project_content, language="java")

            # 2. Aba AGENTES (lista + estatísticas + arquivos ASL/Java/Outros)
            with tab2:
                st.subheader("Agentes Identificados")
                agents = get_all_agents(selected_project, project_content)
                if agents:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write("**Lista de Agentes:**")
                        for i, agent in enumerate(agents, 1):
                            st.write(f"{i}. `{agent}`")
                        # estatísticas de origem
                        mas2j_agents = parse_mas2j(project_content)
                        asl_agents = parse_asl_files(selected_project, project_content)
                        st.write("**Origem dos Agentes:**")
                        st.write(f"- Do arquivo .mas2j: {len(mas2j_agents)} agentes")
                        st.write(f"- Dos arquivos .asl: {len(asl_agents)} agentes")
                        st.write(f"- **Total único:** {len(agents)} agentes")
                    with col2:
                        st.write("**Estatísticas:**")
                        st.metric("Total de Agentes", len(agents))
                        all_files = get_all_project_files(selected_project, project_content)
                        asl_files = [f for f in all_files if f.suffix.lower() == '.asl']
                        st.metric("Arquivos .asl", len(asl_files))

                    # seção de arquivos (antes na aba "Arquivos")
                    st.subheader("Arquivos do Projeto")
                    if all_files:
                        asl_files = [f for f in all_files if f.suffix.lower() == '.asl']
                        java_files = [f for f in all_files if f.suffix.lower() == '.java']
                        other_files = [f for f in all_files if f.suffix.lower() not in ['.asl', '.java']]
                        if asl_files:
                            st.subheader("🔧 Arquivos ASL (Agentes)")
                            for file in asl_files:
                                with st.expander(f"📄 {file.name}"):
                                    try:
                                        with open(file, 'r', encoding='utf-8') as f:
                                            file_content = f.read()
                                        st.code(file_content, language="lisp")
                                    except Exception as e:
                                        st.error(f"Erro ao ler arquivo {file.name}: {e}")
                        if java_files:
                            st.subheader("☕ Arquivos Java")
                            for file in java_files:
                                with st.expander(f"📄 {file.name}"):
                                    try:
                                        with open(file, 'r', encoding='utf-8') as f:
                                            file_content = f.read()
                                        st.code(file_content, language="java")
                                    except Exception as e:
                                        st.error(f"Erro ao ler arquivo {file.name}: {e}")
                        if other_files:
                            st.subheader("📄 Outros Arquivos")
                            for file in other_files:
                                with st.expander(f"📄 {file.name}"):
                                    try:
                                        with open(file, 'r', encoding='utf-8') as f:
                                            file_content = f.read()
                                        language = get_file_language(file)
                                        st.code(file_content, language=language)
                                    except Exception as e:
                                        st.error(f"Erro ao ler arquivo {file.name}: {e}")
                    else:
                        st.info("Nenhum arquivo adicional encontrado")
                else:
                    st.warning("⚠️ Nenhum agente identificado no projeto!")
                    st.info("""
                    💡 Dicas para identificação de agentes:
                    - Verifique se o arquivo .mas2j segue o formato correto
                    - Os arquivos .asl devem conter definições de agentes
                    - Nomes de agentes são geralmente detectados de:
                      * Definições no arquivo .mas2j
                      * Goals (!nome_do_agente) nos arquivos .asl
                      * Nomes dos arquivos .asl (sem extensão)
                    """)

            # 3. Aba SIMULAÇÃO
            with tab3:
                st.subheader("Simulação de Execução")
                agents = get_all_agents(selected_project, project_content)
                if agents:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        simulation_speed = st.select_slider(
                            "Velocidade da simulação:",
                            options=["Lenta", "Normal", "Rápida"],
                            value="Rápida"
                        )
                        if st.button("▶️ Iniciar Simulação", type="primary"):
                            st.session_state.run_simulation = True
                            if 'agent_history' in st.session_state:
                                del st.session_state.agent_history
                            if 'agent_messages' in st.session_state:
                                del st.session_state.agent_messages
                    if st.session_state.get('run_simulation', False):
                        logs, agent_history, agent_messages = simulate_communication(agents)
                        log_container = st.container()
                        with log_container:
                            st.write("**Logs de Execução:**")
                            log_display = st.empty()
                            current_logs = []
                            for log in logs:
                                current_logs.append(log)
                                delay_map = {"Lenta": 1.0, "Normal": 0.5, "Rápida": 0.1}
                                time.sleep(delay_map[simulation_speed])
                                log_text = "\n".join(current_logs)
                                log_display.code(log_text)
                        st.session_state.agent_history = agent_history
                        st.session_state.agent_messages = agent_messages
                        st.session_state.run_simulation = False
                        st.success("🎉 Simulação concluída!")
                    if 'agent_history' in st.session_state and st.session_state.agent_history:
                        st.subheader("📊 Histórico dos Agentes")
                        agent_tabs = st.tabs([f"👤 {agent}" for agent in agents])
                        for i, agent in enumerate(agents):
                            with agent_tabs[i]:
                                history_df = create_agent_history_table(st.session_state.agent_history, agent)
                                if not history_df.empty:
                                    st.write(f"**Histórico do Agente {agent}**")
                                    st.dataframe(history_df, use_container_width=True)
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Total de Ciclos", len(history_df))
                                    with col2:
                                        total_beliefs = sum(len(beliefs.split(',')) for beliefs in history_df['Crenças'])
                                        st.metric("Total de Crenças", total_beliefs)
                                    with col3:
                                        total_goals = sum(len(goals.split(',')) for goals in history_df['Metas'])
                                        st.metric("Total de Metas", total_goals)
                                else:
                                    st.warning(f"Nenhum histórico disponível para o agente {agent}")
                else:
                    st.error("❌ Não é possível simular: nenhum agente encontrado")

            # 4. Aba LOGS
            with tab4:
                st.subheader("📝 Logs dos Agentes")
                if 'agent_messages' in st.session_state and st.session_state.agent_messages:
                    messages_df = create_messages_table(st.session_state.agent_messages)
                    if not messages_df.empty:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total de Mensagens", len(messages_df))
                        with col2:
                            unique_agents = messages_df['Agente'].nunique()
                            st.metric("Agentes Ativos", unique_agents)
                        with col3:
                            send_count = messages_df['Mensagem'].str.contains('\\[SEND\\]').sum()
                            recv_count = messages_df['Mensagem'].str.contains('\\[RECV\\]').sum()
                            st.metric("Env/Recv", f"{send_count}/{recv_count}")
                        st.subheader("Filtros")
                        col1, col2 = st.columns(2)
                        with col1:
                            all_agents = ["Todos"] + list(messages_df['Agente'].unique())
                            selected_agent = st.selectbox("Filtrar por agente:", all_agents)
                        with col2:
                            message_types = ["Todos", "INIT", "SEND", "RECV", "BROADCAST", "INFO"]
                            selected_type = st.selectbox("Filtrar por tipo:", message_types)
                        filtered_df = messages_df.copy()
                        if selected_agent != "Todos":
                            filtered_df = filtered_df[filtered_df['Agente'] == selected_agent]
                        if selected_type != "Todos":
                            filtered_df = filtered_df[filtered_df['Mensagem'].str.contains(f'\\[{selected_type}\\]')]
                        st.write(f"**Mensagens dos Agentes** ({len(filtered_df)} mensagens)")
                        st.dataframe(filtered_df, use_container_width=True)
                        csv = filtered_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Exportar logs como CSV",
                            data=csv,
                            file_name=f"logs_{selected_project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("Nenhuma mensagem disponível")
                else:
                    st.info("Execute a simulação primeiro para ver os logs dos agentes")

            # 5. Aba SNIFFER
            with tab5:
                st.subheader("📊 Sniffer Agent")
                if 'agent_messages' in st.session_state and st.session_state.agent_messages:
                    agents = get_all_agents(selected_project, project_content)
                    if agents:
                        st.subheader("Diagrama de Comunicação")
                        comm_diagram = create_communication_diagram(st.session_state.agent_messages, agents)
                        if comm_diagram:
                            st.plotly_chart(comm_diagram, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True, 'responsive': True})
                            st.markdown("""
                            **Legenda do Diagrama:**
                            - 🔵 **SEND**: Mensagem enviada de um agente para outro
                            - 🟢 **RECV**: Mensagem recebida de outro agente  
                            - 🟠 **BROADCAST**: Mensagem enviada para todos os agentes
                            - 🟣 **INFORM**: Mensagem informativa geral
                            - 🔴 **REQUEST**: Mensagem de requisição
                            - Cada linha vertical representa um agente
                            - As setas mostram a direção da comunicação
                            - A posição vertical representa a sequência temporal
                            """)
                            st.subheader("Tabela de Comunicação - Sniffer Agent")
                            sniffer_table = create_sniffer_table(st.session_state.agent_messages, agents)
                            if sniffer_table is not None:
                                st.dataframe(sniffer_table, use_container_width=True)
                                total_messages = len([m for m in st.session_state.agent_messages if any(tag in m['Mensagem'] for tag in ['SEND', 'RECV', 'BROADCAST', 'INFORM', 'REQUEST'])])
                                send_count = len([m for m in st.session_state.agent_messages if '[SEND]' in m['Mensagem']])
                                recv_count = len([m for m in st.session_state.agent_messages if '[RECV]' in m['Mensagem']])
                                broadcast_count = len([m for m in st.session_state.agent_messages if '[BROADCAST]' in m['Mensagem']])
                                inform_count = len([m for m in st.session_state.agent_messages if '[INFORM]' in m['Mensagem']])
                                request_count = len([m for m in st.session_state.agent_messages if '[REQUEST]' in m['Mensagem']])
                                col1, col2, col3, col4, col5 = st.columns(5)
                                with col1:
                                    st.metric("Total Mensagens", total_messages)
                                with col2:
                                    st.metric("Envios (SEND)", send_count)
                                with col3:
                                    st.metric("Recebimentos (RECV)", recv_count)
                                with col4:
                                    st.metric("Broadcasts", broadcast_count)
                                with col5:
                                    st.metric("Inform/Request", f"{inform_count}/{request_count}")
                                st.subheader("Análise de Padrões de Comunicação")
                                comm_matrix = {}
                                for agent in agents:
                                    comm_matrix[agent] = {}
                                    for other_agent in agents:
                                        comm_matrix[agent][other_agent] = 0
                                for msg in st.session_state.agent_messages:
                                    if '[SEND]' in msg['Mensagem'] and 'para' in msg['Mensagem']:
                                        match = re.search(r'para (\w+):', msg['Mensagem'])
                                        if match:
                                            target_agent = match.group(1)
                                            if target_agent in agents:
                                                comm_matrix[msg['Agente']][target_agent] += 1
                                st.write("**Matriz de Comunicação (envios):**")
                                comm_df = pd.DataFrame(comm_matrix).fillna(0).astype(int)
                                st.dataframe(comm_df, use_container_width=True)
                            else:
                                st.info("Nenhuma mensagem de comunicação encontrada para exibir na tabela sniffer.")
                        else:
                            st.info("Não foi possível gerar o diagrama de comunicação.")
                    else:
                        st.warning("Nenhum agente encontrado no projeto para exibir o sniffer.")
                else:
                    st.info("Execute a simulação primeiro para visualizar o Sniffer Agent.")

            # 6. Aba TROPOS MODELER
            with tab6:
                st.subheader("🖧 Tropos Modeler - SVG Symbols")
                agents = get_all_agents(selected_project, project_content)
                if not agents:
                    st.warning("Nenhum agente encontrado.")
                else:
                    st.write("### Diagrama Tropos – ícones SVG com zoom/pan/download")
                    tropos = {k: [] for k in ("agents", "roles", "goals", "softgoals", "tasks", "dependencies")}
                    all_files = get_all_project_files(selected_project, project_content)
                    asl_files = [f for f in all_files if f.suffix.lower() == '.asl']
                    for asl_file in asl_files:
                        try:
                            with open(asl_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                            content = re.sub(r'//.*?$|/\*.*?\*/', '', content, flags=re.MULTILINE | re.DOTALL)
                            agent_name = asl_file.stem
                            tropos["agents"].append(agent_name)
                            role = "Manager" if "manager" in agent_name.lower() else "Provider" if "provider" in agent_name.lower() else "Worker"
                            tropos["roles"].append((agent_name, role))
                            goals = re.findall(r'!(\w+)', content)
                            softgoals = re.findall(r'!(\w+_\w+)', content)
                            tasks = re.findall(r'\+!(\w+).*?<-', content, re.DOTALL)
                            tropos["goals"].extend([(g, agent_name) for g in goals])
                            tropos["softgoals"].extend([(sg, agent_name) for sg in softgoals])
                            tropos["tasks"].extend([(t, agent_name) for t in tasks])
                            sends = re.findall(r'send\((\w+),', content)
                            for target in sends:
                                if target != agent_name and target in agents:
                                    tropos["dependencies"].append((agent_name, target, "depends-on"))
                        except Exception as e:
                            st.warning(f"Erro ao processar {asl_file.name}: {e}")
                    for k in tropos:
                        if isinstance(tropos[k], list):
                            tropos[k] = list(set(tropos[k]))
                    import base64
                    def svg_b64(name):
                        path = Path("symbols") / f"{name}.svg"
                        if not path.exists():
                            svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><rect width="60" height="60" fill="lightblue"/><text x="50%" y="50%" text-anchor="middle" dy=".3em">{name}</text></svg>'
                        else:
                            svg = path.read_text(encoding="utf-8")
                        return base64.b64encode(svg.encode()).decode()
                    COL_W, ROW_H = 200, 150
                    svg_width = max(len(tropos["agents"]) * COL_W, 800)
                    fig = go.Figure()
                    dy = 70
                    dx = 30
                    for i, agent in enumerate(tropos["agents"]):
                        x, y = i * COL_W + COL_W/2, ROW_H/2
                        fig.add_layout_image(x=x, y=y, sizex=60, sizey=60, xref="x", yref="y", opacity=1,
                                             source=f"data:image/svg+xml;base64,{svg_b64('agent')}")
                        fig.add_annotation(x=x+dx, y=y-dy, text=f"<b>{agent}</b>", showarrow=False, font=dict(size=14), bgcolor="rgba(255,255,255,0)")
                    for i, (agent, role) in enumerate(tropos["roles"]):
                        x, y = i * COL_W + COL_W/2, ROW_H + ROW_H/2
                        fig.add_layout_image(x=x, y=y, sizex=60, sizey=60, xref="x", yref="y", opacity=1,
                                             source=f"data:image/svg+xml;base64,{svg_b64('role')}")
                        fig.add_annotation(x=x+dx, y=y-dy, text=f"<b>{role}</b>", showarrow=False, font=dict(size=14), bgcolor="rgba(255,255,255,0)")
                    for i, (goal, agent) in enumerate(tropos["goals"]):
                        x, y = i * COL_W + COL_W/2, 2*ROW_H + ROW_H/2
                        fig.add_layout_image(x=x, y=y, sizex=120, sizey=60, xref="x", yref="y", opacity=1,
                                             source=f"data:image/svg+xml;base64,{svg_b64('goal')}")
                        fig.add_annotation(x=x+dx, y=y-dy, text=f"<b>{goal}</b>", showarrow=False, font=dict(size=14), bgcolor="rgba(255,255,255,0)")
                    for i, (sg, agent) in enumerate(tropos["softgoals"]):
                        x, y = i * COL_W + COL_W/2, 3*ROW_H + ROW_H/2
                        fig.add_layout_image(x=x, y=y, sizex=120, sizey=60, xref="x", yref="y", opacity=1,
                                             source=f"data:image/svg+xml;base64,{svg_b64('softgoal')}")
                        fig.add_annotation(x=x+dx, y=y-dy, text=f"<b>{sg}</b>", showarrow=False, font=dict(size=14), bgcolor="rgba(255,255,255,0)")
                    for i, (task, agent) in enumerate(tropos["tasks"]):
                        x, y = i * COL_W + COL_W/2, 4*ROW_H + ROW_H/2
                        fig.add_layout_image(x=x, y=y, sizex=120, sizey=60, xref="x", yref="y", opacity=1,
                                             source=f"data:image/svg+xml;base64,{svg_b64('task')}")
                        fig.add_annotation(x=x+dx, y=y-dy, text=f"<b>{task}</b>", showarrow=False, font=dict(size=14), bgcolor="rgba(255,255,255,0)")
                    for src, dst, dep in tropos["dependencies"]:
                        if src in tropos["agents"] and dst in tropos["agents"]:
                            x0 = tropos["agents"].index(src) * COL_W + COL_W/2
                            x1 = tropos["agents"].index(dst) * COL_W + COL_W/2
                            y = ROW_H/2
                            fig.add_annotation(
                                x=x1, y=y, ax=x0, ay=y,
                                xref="x", yref="y", axref="x", ayref="y",
                                showarrow=True, arrowhead=2, arrowcolor="gray",
                                arrowwidth=3, arrowsize=1.2, standoff=3
                            )
                    fig.update_xaxes(range=[-COL_W/2, svg_width + COL_W/2], visible=False)
                    fig.update_yaxes(range=[-50, 5*ROW_H + 50], visible=False)
                    fig.update_layout(title="Diagrama Tropos – Plotly + SVG", height=5*ROW_H + 120,
                                      margin=dict(l=40, r=40, t=60, b=40),
                                      plot_bgcolor="white", dragmode="zoom", showlegend=False)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'scrollZoom': True})
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.download_button("📥 Exportar Tropos TXT", data=str(tropos).encode('utf-8'),
                                           file_name=f"tropos_{selected_project_name}.txt", mime="text/plain")
                    with col2:
                        import csv, io
                        csv_buffer = io.StringIO()
                        writer = csv.writer(csv_buffer)
                        writer.writerow(["Categoria", "Elemento", "Agente"])
                        for cat, lista in tropos.items():
                            if cat in {"goals", "softgoals", "tasks"}:
                                for elem, agent in lista:
                                    writer.writerow([cat, elem, agent])
                            elif cat in {"roles"}:
                                for agent, role in lista:
                                    writer.writerow([cat, role, agent])
                            elif cat in {"agents", "actors"}:
                                for agent in lista:
                                    writer.writerow([cat, agent, ""])
                            elif cat in {"dependencies"}:
                                for src, dst, dep in lista:
                                    writer.writerow([cat, f"{src} -> {dst}", dep])
                            elif cat in {"contributions"}:
                                for src, dst, contrib in lista:
                                    writer.writerow([cat, f"{src} -{contrib}-> {dst}", ""])
                        st.download_button("📥 Exportar Tropos CSV", data=csv_buffer.getvalue().encode('utf-8'),
                                           file_name=f"tropos_{selected_project_name}.csv", mime="text/csv")
                    with col3:
                        st.download_button("📥 Exportar SVG", data=f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{5*ROW_H+120}">...</svg>'.encode('utf-8'),
                                           file_name=f"tropos_{selected_project_name}.svg", mime="image/svg+xml")

else:
    st.error("📂 Nenhum projeto encontrado na pasta './projects'")
    st.info("""
    **Estrutura do projeto necessária:**
    ```
    seu-repositorio/
    ├── app.py
    ├── requirements.txt
    └── projects/
        ├── projeto1/
        │   ├── projeto1.mas2j
        │   ├── agente1.asl
        │   └── agente2.asl
        ├── projeto2/
        │   ├── projeto2.mas2j
        │   └── src/
        │       ├── asl/
        │       │   └── agentes.asl
        │       └── java/
        │           └── Environment.java
        └── projeto3/
            ├── projeto3.mas3j
            └── scripts.asl
    """)

st.markdown("---")
st.caption("Desenvolvido para análise de sistemas multiagente")

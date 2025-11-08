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
    
    # Encontra todas as subpastas dentro de ./projects
    project_folders = [f for f in project_dir.iterdir() if f.is_dir()]
    
    projects = []
    
    for folder in project_folders:
        # Procura por arquivos .mas2j ou .mas3j dentro da pasta do projeto
        mas_files = list(folder.glob("*.mas2j")) + list(folder.glob("*.mas3j"))
        
        if mas_files:
            # Usa o primeiro arquivo .mas2j/.mas3j encontrado como arquivo principal do projeto
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
        # Fallback para o comportamento antigo
        project_path = PROJECT_ROOT / "projects" / project_info
    
    if project_path.exists():
        try:
            with open(project_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Tenta latin-1 se utf-8 falhar
            with open(project_path, 'r', encoding='latin-1') as file:
                return file.read()
    else:
        st.error(f"Arquivo não encontrado: {project_path}")
    return None

def parse_project_paths(file_content):
    """Extrai os caminhos do projeto do conteúdo do arquivo .mas2j"""
    # Remove comentários para facilitar o parsing
    content_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', file_content, flags=re.MULTILINE | re.DOTALL)
    
    paths = {}
    
    # Procura pelo aslSourcePath
    asl_pattern = r'aslSourcePath\s*:\s*"([^"]+)"'
    asl_match = re.search(asl_pattern, content_no_comments)
    if asl_match:
        paths['asl_source_path'] = asl_match.group(1)
    
    # Procura pelo classPath
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
        
        # Primeiro, procura por todos os arquivos na pasta raiz do projeto
        root_files = [f for f in folder.iterdir() if f.is_file()]
        all_files.extend([
            f for f in root_files 
            if f.suffix.lower() not in ['.mas2j', '.mas3j']
        ])
        
        # Se temos o conteúdo do projeto, procura nos caminhos especificados
        if project_content:
            paths = parse_project_paths(project_content)
            
            # Procura arquivos no aslSourcePath
            if 'asl_source_path' in paths:
                asl_path = folder / paths['asl_source_path']
                if asl_path.exists() and asl_path.is_dir():
                    # Procura por todos os arquivos no aslSourcePath (não apenas .asl)
                    asl_files = list(asl_path.rglob("*"))
                    all_files.extend([f for f in asl_files if f.is_file()])
            
            # Procura arquivos no classPath
            if 'class_path' in paths:
                class_path = folder / paths['class_path']
                if class_path.exists() and class_path.is_dir():
                    # Procura por todos os arquivos no classPath
                    class_files = list(class_path.rglob("*"))
                    all_files.extend([f for f in class_files if f.is_file()])
        
        # Remove duplicatas
        seen_files = set()
        unique_files = []
        
        for file in all_files:
            if file.name not in seen_files:
                seen_files.add(file.name)
                unique_files.append(file)
        
        return unique_files
    
    return []

def parse_mas2j(file_content):
    """Faz o parsing de um arquivo .mas2j para extrair agentes - versão melhorada"""
    agents = []
    
    # Remove comentários para facilitar o parsing
    content_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', file_content, flags=re.MULTILINE | re.DOTALL)
    
    # Múltiplos padrões para capturar diferentes formatos de definição de agentes
    
    # Padrão 1: agentes em múltiplas linhas com atributos (seu formato)
    pattern1 = r'agents\s*:\s*((?:\w+\s*(?:\[.*?\])?(?:\s*at\s*"[^"]*")?\s*;?\s*)+)'
    match1 = re.search(pattern1, content_no_comments, re.DOTALL)
    if match1:
        agents_section = match1.group(1)
        # Extrai nomes dos agentes (palavras antes de [ ou at ou ;)
        agent_names = re.findall(r'(\w+)\s*(?:\[|\bat\b|;)', agents_section)
        agents.extend(agent_names)
    
    # Padrão 2: agentes entre chaves
    pattern2 = r'agents\s*:\s*\{([^}]+)\}'
    match2 = re.search(pattern2, content_no_comments, re.DOTALL)
    if match2:
        agents_section = match2.group(1)
        agent_names = re.findall(r'(\w+)\s*(?:\[|\bat\b|;|$)', agents_section)
        agents.extend(agent_names)
    
    # Padrão 3: agentes em linha única
    pattern3 = r'agents?\s*:\s*((?:\w+\s*)+);'
    match3 = re.search(pattern3, content_no_comments)
    if match3:
        agents_section = match3.group(1)
        agent_names = re.findall(r'\w+', agents_section)
        agents.extend(agent_names)
    
    # Padrão 4: definições individuais de agentes
    pattern4 = r'agent\s+(\w+)\s*(?:\[.*?\])?(?:\s*at\s*"[^"]*")?\s*;'
    agents.extend(re.findall(pattern4, content_no_comments))
    
    # Remove duplicatas e limpa resultados
    agents = list(set(agents))
    
    # Filtra palavras que não são agentes (remover palavras-chave comuns)
    keywords = ['infrastructure', 'environment', 'aslSourcePath', 'classPath', 
                'initialisation', 'launchParameters', 'agents', 'agent']
    agents = [agent for agent in agents if agent not in keywords and len(agent) > 1]
    
    return agents

def parse_asl_files(project_info, project_content=None):
    """Extrai agentes de arquivos .asl - nova função para detectar agentes nos arquivos ASL"""
    asl_agents = []
    
    # Obtém todos os arquivos do projeto
    all_files = get_all_project_files(project_info, project_content)
    
    # Filtra apenas arquivos .asl
    asl_files = [f for f in all_files if f.suffix.lower() == '.asl']
    
    for asl_file in asl_files:
        try:
            # Tenta ler o arquivo com diferentes encodings
            try:
                with open(asl_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(asl_file, 'r', encoding='latin-1') as f:
                    content = f.read()
            
            # Remove comentários para facilitar o parsing
            content_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', content, flags=re.MULTILINE | re.DOTALL)
            
            # Padrão 1: Busca por definições de agentes no formato Jason/AgentSpeak
            # Procura por padrões como: !agent_name ou +!goal
            agent_patterns = [
                r'!(\w+)',  # Goals que podem indicar nomes de agentes
                r'\+\s*!(\w+)',  # Adição de goals
                r'@(\w+)',  # Annotations que podem conter nomes de agentes
                r'agent\s*:\s*(\w+)',  # Definição explícita de agente
                r'(\w+)\s*\{',  # Possível definição de agente com chaves
            ]
            
            for pattern in agent_patterns:
                matches = re.findall(pattern, content_no_comments)
                asl_agents.extend(matches)
            
            # Padrão 2: Busca por includes que podem referenciar agentes
            include_pattern = r'include\s*"([^"]+)"'
            includes = re.findall(include_pattern, content_no_comments)
            for include in includes:
                # Se o include não tem extensão ou tem extensão .asl, pode ser um agente
                if '.' not in include or include.endswith('.asl'):
                    agent_name = include.replace('.asl', '')
                    asl_agents.append(agent_name)
            
            # Padrão 3: O nome do arquivo sem extensão pode ser o nome do agente
            agent_name_from_file = asl_file.stem
            if agent_name_from_file and agent_name_from_file not in ['environment', 'utils', 'common']:
                asl_agents.append(agent_name_from_file)
                
        except Exception as e:
            st.warning(f"Erro ao processar arquivo {asl_file.name}: {e}")
    
    # Remove duplicatas e limpa resultados
    asl_agents = list(set(asl_agents))
    
    # Filtra palavras que não são agentes
    keywords = ['true', 'false', 'not', 'and', 'or', 'if', 'then', 'else', 'forall', 
                'bel', 'goal', 'test', 'plan', 'source', 'self', 'percept', 'action',
                'internal', 'external', 'init', 'main', 'stop', 'print', 'send', 'broadcast']
    asl_agents = [agent for agent in asl_agents if agent not in keywords and len(agent) > 1]
    
    return asl_agents

def get_all_agents(project_info, project_content):
    """Combina agentes do arquivo .mas2j e dos arquivos .asl"""
    mas2j_agents = parse_mas2j(project_content)
    asl_agents = parse_asl_files(project_info, project_content)
    
    # Combina as listas e remove duplicatas
    all_agents = list(set(mas2j_agents + asl_agents))
    
    # Ordena alfabeticamente para consistência
    all_agents.sort()
    
    return all_agents

def simulate_communication(agents):
    """Simula a comunicação entre agentes e retorna logs, histórico e mensagens"""
    logs = []
    agent_history = {agent: [] for agent in agents}
    agent_messages = []  # Nova lista para armazenar mensagens dos agentes
    
    if not agents:
        logs.append("⚠️ Nenhum agente encontrado para simular comunicação")
        return logs, agent_history, agent_messages
    
    # Tempo inicial de referência
    start_time = datetime.now()
    
    # Inicialização dos agentes
    logs.append("🚀 Iniciando sistema multiagente...")
    
    for agent in agents:
        logs.append(f"✅ {agent} inicializado")
        
        # Adiciona mensagem de inicialização
        current_time = datetime.now()
        elapsed = current_time - start_time
        milliseconds = int(elapsed.total_seconds() * 1000)
        timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
        
        agent_messages.append({
            'Hora': timestamp,
            'Agente': agent,
            'Mensagem': f"[INIT] Agente {agent} inicializado com sucesso"
        })
        
        agent_history[agent].append({
            'Hora': timestamp,
            'Ciclo': 0,
            'Crenças': "sistema_iniciado, pronto_para_comunicar",
            'Metas': "inicializar_sistema"
        })
    
    logs.append("---")
    logs.append("📨 Iniciando comunicação entre agentes...")
    
    # Simula diferentes padrões de comunicação
    for cycle, sender in enumerate(agents, 1):
        # Cada agente envia mensagem para o próximo (anéis)
        receiver = agents[(cycle) % len(agents)]
        
        # Atualiza histórico do sender
        current_time = datetime.now()
        elapsed = current_time - start_time
        milliseconds = int(elapsed.total_seconds() * 1000)
        timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
        
        # Mensagem de envio
        agent_messages.append({
            'Hora': timestamp,
            'Agente': sender,
            'Mensagem': f"[SEND] Enviando mensagem para {receiver}: 'Olá {receiver}!'"
        })
        
        agent_history[sender].append({
            'Hora': timestamp,
            'Ciclo': cycle,
            'Crenças': f"enviando_msg_para_{receiver}, comunicacao_ativa",
            'Metas': f"enviar_mensagem_{receiver}, manter_conexao"
        })
        
        logs.append(f"📤 {sender} → {receiver}: Mensagem de saudação")
        
        # Pequena pausa entre ações
        time.sleep(0.1)
        
        # Atualiza histórico do receiver
        current_time = datetime.now()
        elapsed = current_time - start_time
        milliseconds = int(elapsed.total_seconds() * 1000)
        timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
        
        # Mensagem de recebimento
        agent_messages.append({
            'Hora': timestamp,
            'Agente': receiver,
            'Mensagem': f"[RECV] Mensagem recebida de {sender}: 'Olá {receiver}!'"
        })
        
        # Mensagem de resposta
        agent_messages.append({
            'Hora': timestamp,
            'Agente': receiver,
            'Mensagem': f"[SEND] Respondendo para {sender}: 'Olá {sender}! Recebida sua mensagem.'"
        })
        
        agent_history[receiver].append({
            'Hora': timestamp,
            'Ciclo': cycle,
            'Crenças': f"recebendo_msg_de_{sender}, mensagem_processada",
            'Metas': f"responder_{sender}, processar_mensagem"
        })
        
        logs.append(f"📥 {receiver} ← {sender}: Confirmação recebida")
        
        # Pequena pausa entre ações
        time.sleep(0.1)
        
        # Mensagem de confirmação do sender
        current_time = datetime.now()
        elapsed = current_time - start_time
        milliseconds = int(elapsed.total_seconds() * 1000)
        timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
        
        agent_messages.append({
            'Hora': timestamp,
            'Agente': sender,
            'Mensagem': f"[RECV] Confirmação recebida de {receiver}"
        })
        
        # Alguns agentes fazem broadcast
        if cycle == 1:
            logs.append(f"📢 {sender} faz broadcast para todos os agentes")
            
            # Mensagem de broadcast
            current_time = datetime.now()
            elapsed = current_time - start_time
            milliseconds = int(elapsed.total_seconds() * 1000)
            timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
            
            agent_messages.append({
                'Hora': timestamp,
                'Agente': sender,
                'Mensagem': f"[BROADCAST] Enviando mensagem para todos os agentes: 'Sincronização iniciada'"
            })
            
            # Atualiza histórico para broadcast
            agent_history[sender].append({
                'Hora': timestamp,
                'Ciclo': cycle,
                'Crenças': "broadcast_enviado, todos_notificados",
                'Metas': "coordenar_agentes, manter_sincronizacao"
            })
            
            # Mensagens de recebimento do broadcast para outros agentes
            for other_agent in agents:
                if other_agent != sender:
                    current_time = datetime.now()
                    elapsed = current_time - start_time
                    milliseconds = int(elapsed.total_seconds() * 1000)
                    timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
                    
                    agent_messages.append({
                        'Hora': timestamp,
                        'Agente': other_agent,
                        'Mensagem': f"[RECV] Broadcast recebido de {sender}: 'Sincronização iniciada'"
                    })
    
    # Ciclo final - mensagens de finalização
    final_cycle = len(agents) + 1
    current_time = datetime.now()
    elapsed = current_time - start_time
    milliseconds = int(elapsed.total_seconds() * 1000)
    timestamp = f"{elapsed.seconds // 3600:02d}:{(elapsed.seconds // 60) % 60:02d}:{elapsed.seconds % 60:02d}.{milliseconds % 1000:03d}"
    
    for agent in agents:
        agent_messages.append({
            'Hora': timestamp,
            'Agente': agent,
            'Mensagem': f"[INFO] Finalizando execução - todas as tarefas concluídas"
        })
        
        agent_history[agent].append({
            'Hora': timestamp,
            'Ciclo': final_cycle,
            'Crenças': "sistema_finalizado, todas_tarefas_concluidas",
            'Metas': "finalizar_processos, aguardar_nova_execucao"
        })
    
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
        '.asl': 'lisp',
        '.java': 'java',
        '.py': 'python',
        '.xml': 'xml',
        '.json': 'json',
        '.txt': 'text',
        '.md': 'markdown',
        '.yml': 'yaml',
        '.yaml': 'yaml',
        '.properties': 'properties',
        '.sh': 'bash',
        '.bat': 'bat',
        '.sql': 'sql',
        '.html': 'html',
        '.css': 'css',
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
    
    # Espaçamento vertical entre as setas
    vertical_spacing = 10.0
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
    
    for i, msg in enumerate(comm_messages):
        message_text = msg['Mensagem']
        agent = msg['Agente']
        y_pos = i * vertical_spacing + 1
        
        # Extrai informações da mensagem
        if '[SEND]' in message_text:
            if 'para' in message_text:
                match = re.search(r'para (\w+):', message_text)
                if match:
                    target_agent = match.group(1)
                    if target_agent in agents:
                        communications.append({
                            'from': agent,
                            'to': target_agent,
                            'message': message_text,
                            'time': msg['Hora'],
                            'type': 'SEND',
                            'y_pos': y_pos
                        })
        
        elif '[BROADCAST]' in message_text:
            for target_agent in agents:
                if target_agent != agent:
                    communications.append({
                        'from': agent,
                        'to': target_agent,
                        'message': message_text,
                        'time': msg['Hora'],
                        'type': 'BROADCAST',
                        'y_pos': y_pos
                    })
        
        elif '[RECV]' in message_text:
            if 'de' in message_text:
                match = re.search(r'de (\w+):', message_text)
                if match:
                    source_agent = match.group(1)
                    if source_agent in agents:
                        communications.append({
                            'from': source_agent,
                            'to': agent,
                            'message': message_text,
                            'time': msg['Hora'],
                            'type': 'RECV',
                            'y_pos': y_pos
                        })
        
        elif '[INFORM]' in message_text:
            communications.append({
                'from': agent,
                'to': 'ALL',
                'message': message_text,
                'time': msg['Hora'],
                'type': 'INFORM',
                'y_pos': y_pos
            })
        
        elif '[REQUEST]' in message_text:
            if 'para' in message_text:
                match = re.search(r'para (\w+):', message_text)
                if match:
                    target_agent = match.group(1)
                    if target_agent in agents:
                        communications.append({
                            'from': agent,
                            'to': target_agent,
                            'message': message_text,
                            'time': msg['Hora'],
                            'type': 'REQUEST',
                            'y_pos': y_pos
                        })
    
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
        
        if comm['type'] == 'BROADCAST':
            y_pos = y_pos + 0.8
        
        if comm['to'] == 'ALL':
            for target_agent in agents:
                if target_agent != comm['from']:
                    fig.add_annotation(
                        x=agent_positions[target_agent],
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
        else:
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
    
    # Adiciona texto das mensagens EM UMA CAMADA SEPARADA para evitar sobreposição
    text_annotations = []
    broadcast_texts_added = set()  # Para evitar duplicação de textos de broadcast

    for comm in communications:
        y_pos = comm['y_pos']
        
        message_short = comm['message'].split(':')[-1].strip().replace("'", "")[:50]
        
        if comm['to'] == 'ALL':
            # Para BROADCAST, adiciona apenas UMA vez o texto centralizado
            if comm['message'] not in broadcast_texts_added:
                # Atribui posições Y sequenciais para broadcasts
                broadcast_count = len(broadcast_texts_added)
                text_y = y_pos + 15.0 + (broadcast_count * 6.0)  # Espaçamento garantido
                
                text_annotations.append(dict(
                    x=len(agents) / 2 - 0.5,
                    y=text_y,
                    text=message_short,
                    showarrow=False,
                    font=dict(size=10, color="darkblue", family="Arial"),
                    opacity=1.0
                ))
                broadcast_texts_added.add(comm['message'])
        else:
            # Para mensagens ponto-a-ponto
            text_annotations.append(dict(
                x=(agent_positions[comm['from']] + agent_positions[comm['to']]) / 2,
                y=y_pos + 4.0,
                text=message_short,
                showarrow=False,
                font=dict(size=10, color="darkblue", family="Arial"),
                opacity=1.0
            ))
    
    # Adiciona todas as anotações de texto de uma vez (SEM CAIXAS)
    for annotation in text_annotations:
        fig.add_annotation(annotation)
    
    # Adiciona retângulos para cada agente
    for agent, x_pos in agent_positions.items():
        # Adiciona retângulo como shape
        fig.add_shape(
            type="rect",
            x0=x_pos - 0.4,
            y0=max_height + 0.5,
            x1=x_pos + 0.4,
            y1=max_height + 10.0,
            line=dict(color="darkblue", width=1),
            fillcolor="lightblue",
            opacity=0.8
        )
        
        # Adiciona texto do agente sem caixa
        fig.add_annotation(
            x=x_pos,
            y=max_height + 5,
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
        height=1000,
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
    
    # Filtra mensagens de comunicação
    comm_messages = [
        msg for msg in agent_messages 
        if any(tag in msg['Mensagem'] for tag in ['[SEND]', '[RECV]', '[BROADCAST]', '[REQUEST]', '[INFORM]'])
    ]
    
    # Cria DataFrame para a tabela
    data = []
    for i, msg in enumerate(comm_messages):
        row = {'Step': i + 1}
        
        # Determina o tipo e conteúdo da mensagem
        message_text = msg['Mensagem']
        agent = msg['Agente']
        
        # Extrai informações específicas
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
        
        # Adiciona a mensagem na coluna do agente correspondente
        for a in agents:
            if a == agent:
                row[a] = f"{msg_type}: {msg_content}"
            else:
                row[a] = ""
        
        data.append(row)
    
    # Cria DataFrame
    if data:
        df = pd.DataFrame(data)
        return df
    return None

# Obtém lista de projetos (pastas)
projects = get_project_folders()
if projects:
    # Cria lista de nomes para o selectbox
    project_names = [project['name'] for project in projects]
    
    # Selectbox para escolher o projeto
    selected_project_name = st.sidebar.selectbox("Selecione um projeto:", project_names, index=0)

    # Verifica se o projeto foi alterado
    if 'current_project' not in st.session_state:
        st.session_state.current_project = selected_project_name
    elif st.session_state.current_project != selected_project_name:
        # Projeto foi alterado - limpa o estado da simulação
        clear_simulation_state()
        st.session_state.current_project = selected_project_name

    # Encontra o projeto selecionado
    selected_project = next((p for p in projects if p['name'] == selected_project_name), None)

    if selected_project:
        # Mostra informações do projeto selecionado
        st.subheader(f"📄 Projeto: {selected_project_name}")
        
        # Carrega e exibe o conteúdo do projeto
        project_content = load_project_file(selected_project)
        
        if project_content:
            # Extrai os caminhos do projeto
            paths = parse_project_paths(project_content)
            
            # Mostra informações da pasta do projeto
            with st.expander("📁 Estrutura do Projeto"):
                st.write(f"**Pasta:** `{selected_project['folder']}`")
                st.write(f"**Arquivo principal:** `{selected_project['main_file'].name}`")
                
                if 'asl_source_path' in paths:
                    st.write(f"**aslSourcePath:** `{paths['asl_source_path']}`")
                
                if 'class_path' in paths:
                    st.write(f"**classPath:** `{paths['class_path']}`")
                
                # Lista todos os arquivos do projeto
                all_files = get_all_project_files(selected_project, project_content)
                if all_files:
                    st.write("**Arquivos do projeto:**")
                    for file in all_files:
                        st.write(f"- `{file.name}`")
                else:
                    st.info("Nenhum arquivo adicional encontrado")
            
            # Abas para organizar as informações
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 Código", "📁 Arquivos", "🤖 Agentes", "🔄 Simulação", "📝 Logs dos Agentes", "📊 Sniffer Agent"])
            
            with tab1:
                st.subheader("Conteúdo do Arquivo Principal")
                st.code(project_content, language="java")
            
            with tab2:
                st.subheader("Arquivos do Projeto")
                all_files = get_all_project_files(selected_project, project_content)
                
                if all_files:
                    # Agrupa arquivos por tipo para melhor organização
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
            
            with tab3:
                st.subheader("Agentes Identificados")
                agents = get_all_agents(selected_project, project_content)
                
                if agents:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write("**Lista de Agentes:**")
                        for i, agent in enumerate(agents, 1):
                            st.write(f"{i}. `{agent}`")
                        
                        # Mostra estatísticas de detecção
                        mas2j_agents = parse_mas2j(project_content)
                        asl_agents = parse_asl_files(selected_project, project_content)
                        
                        st.write("**Origem dos Agentes:**")
                        st.write(f"- Do arquivo .mas2j: {len(mas2j_agents)} agentes")
                        st.write(f"- Dos arquivos .asl: {len(asl_agents)} agentes")
                        st.write(f"- **Total único:** {len(agents)} agentes")
                    
                    with col2:
                        st.write("**Estatísticas:**")
                        st.metric("Total de Agentes", len(agents))
                        
                        # Mostra contagem de arquivos .asl
                        all_files = get_all_project_files(selected_project, project_content)
                        asl_files = [f for f in all_files if f.suffix.lower() == '.asl']
                        st.metric("Arquivos .asl", len(asl_files))
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
            
            with tab4:
                st.subheader("Simulação de Execução")
                agents = get_all_agents(selected_project, project_content)
                
                if agents:
                    # Controles de simulação
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        simulation_speed = st.select_slider(
                            "Velocidade da simulação:",
                            options=["Lenta", "Normal", "Rápida"]
                        )
                        
                        if st.button("▶️ Iniciar Simulação", type="primary"):
                            st.session_state.run_simulation = True
                            # Limpar histórico anterior se existir
                            if 'agent_history' in st.session_state:
                                del st.session_state.agent_history
                            if 'agent_messages' in st.session_state:
                                del st.session_state.agent_messages
                    
                    # Executa simulação se solicitado
                    if st.session_state.get('run_simulation', False):
                        logs, agent_history, agent_messages = simulate_communication(agents)
                        
                        # Container para logs
                        log_container = st.container()
                        with log_container:
                            st.write("**Logs de Execução:**")
                            log_display = st.empty()
                            
                            # Simula execução em tempo real
                            current_logs = []
                            for log in logs:
                                current_logs.append(log)
                                
                                # Atraso baseado na velocidade selecionada
                                delay_map = {"Lenta": 1.0, "Normal": 0.5, "Rápida": 0.1}
                                time.sleep(delay_map[simulation_speed])
                                
                                # Atualiza display
                                log_text = "\n".join(current_logs)
                                log_display.code(log_text)
                        
                        # Salva o histórico e mensagens na session state
                        st.session_state.agent_history = agent_history
                        st.session_state.agent_messages = agent_messages
                        st.session_state.run_simulation = False
                        st.success("🎉 Simulação concluída!")
                    
                    # Mostrar histórico dos agentes se disponível
                    if 'agent_history' in st.session_state and st.session_state.agent_history:
                        st.subheader("📊 Histórico dos Agentes")
                        
                        # Cria abas para cada agente
                        agent_tabs = st.tabs([f"👤 {agent}" for agent in agents])
                        
                        for i, agent in enumerate(agents):
                            with agent_tabs[i]:
                                history_df = create_agent_history_table(st.session_state.agent_history, agent)
                                if not history_df.empty:
                                    st.write(f"**Histórico do Agente {agent}**")
                                    st.dataframe(history_df, use_container_width=True)
                                    
                                    # Estatísticas do agente
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
            
            with tab5:
                st.subheader("📝 Logs dos Agentes")
                
                # Mostrar tabela de mensagens se disponível
                if 'agent_messages' in st.session_state and st.session_state.agent_messages:
                    messages_df = create_messages_table(st.session_state.agent_messages)
                    
                    if not messages_df.empty:
                        # Estatísticas das mensagens
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
                        
                        # Filtros para a tabela
                        st.subheader("Filtros")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            all_agents = ["Todos"] + list(messages_df['Agente'].unique())
                            selected_agent = st.selectbox("Filtrar por agente:", all_agents)
                        
                        with col2:
                            message_types = ["Todos", "INIT", "SEND", "RECV", "BROADCAST", "INFO"]
                            selected_type = st.selectbox("Filtrar por tipo:", message_types)
                        
                        # Aplicar filtros
                        filtered_df = messages_df.copy()
                        
                        if selected_agent != "Todos":
                            filtered_df = filtered_df[filtered_df['Agente'] == selected_agent]
                        
                        if selected_type != "Todos":
                            filtered_df = filtered_df[filtered_df['Mensagem'].str.contains(f'\\[{selected_type}\\]')]
                        
                        # Mostrar tabela filtrada
                        st.write(f"**Mensagens dos Agentes** ({len(filtered_df)} mensagens)")
                        st.dataframe(filtered_df, use_container_width=True)
                        
                        # Botão para exportar dados
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

            with tab6:
                st.subheader("📊 Sniffer Agent")
                
                if 'agent_messages' in st.session_state and st.session_state.agent_messages:
                    agents = get_all_agents(selected_project, project_content)
                    
                    if agents:
                        # Cria o diagrama de comunicação
                        st.subheader("Diagrama de Comunicação")
                        comm_diagram = create_communication_diagram(st.session_state.agent_messages, agents)
                        
                        if comm_diagram:
                            # Renderizar o gráfico
                            st.plotly_chart(comm_diagram, use_container_width=True, config={
                                'scrollZoom': True,
                                'displayModeBar': True,
                                'responsive': True
                            })
                            
                            # Legenda detalhada
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
                            
                            # Tabela estilo sniffer
                            st.subheader("Tabela de Comunicação - Sniffer Agent")
                            sniffer_table = create_sniffer_table(st.session_state.agent_messages, agents)
                            
                            if sniffer_table is not None:
                                # Renderizar a tabela
                                st.dataframe(sniffer_table, use_container_width=True)
                                
                                # Estatísticas de comunicação
                                st.subheader("Estatísticas de Comunicação")
                                
                                total_messages = len([m for m in st.session_state.agent_messages 
                                                    if any(tag in m['Mensagem'] for tag in ['SEND', 'RECV', 'BROADCAST', 'INFORM', 'REQUEST'])])
                                
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
                                
                                # Análise de padrões de comunicação
                                st.subheader("Análise de Padrões de Comunicação")
                                
                                # Calcula matriz de comunicação
                                comm_matrix = {}
                                for agent in agents:
                                    comm_matrix[agent] = {}
                                    for other_agent in agents:
                                        comm_matrix[agent][other_agent] = 0
                                
                                # Preenche a matriz
                                for msg in st.session_state.agent_messages:
                                    if '[SEND]' in msg['Mensagem'] and 'para' in msg['Mensagem']:
                                        match = re.search(r'para (\w+):', msg['Mensagem'])
                                        if match:
                                            target_agent = match.group(1)
                                            if target_agent in agents:
                                                comm_matrix[msg['Agente']][target_agent] += 1
                                
                                # Mostra matriz de comunicação
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
    ```
    """)

# Footer
st.markdown("---")
st.caption("Desenvolvido para análise de sistemas multiagente")

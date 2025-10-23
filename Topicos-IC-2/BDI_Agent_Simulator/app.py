import streamlit as st
import xml.etree.ElementTree as ET
import re
import os
from pathlib import Path
import time
from datetime import datetime
import pandas as pd

PROJECT_ROOT = Path(__file__).parent

def get_project_files():
    """Obtém a lista de arquivos .mas2j da pasta projects"""
    project_dir = PROJECT_ROOT / "projects"

    if project_dir.exists():
        mas2j_files = list(project_dir.glob("*.mas2j"))
        mas3j_files = list(project_dir.glob("*.mas3j"))
        return mas2j_files + mas3j_files
    return []

def load_project_file(filename):
    """Carrega o conteúdo de um arquivo de projeto"""
    project_path = PROJECT_ROOT / "projects" / filename
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

def simulate_communication(agents):
    """Simula a comunicação entre agentes e retorna logs e histórico"""
    logs = []
    agent_history = {agent: [] for agent in agents}
    
    if not agents:
        logs.append("⚠️ Nenhum agente encontrado para simular comunicação")
        return logs, agent_history
    
    # Inicialização dos agentes
    logs.append("🚀 Iniciando sistema multiagente...")
    
    for agent in agents:
        logs.append(f"✅ {agent} inicializado")
        # Adiciona ao histórico
        agent_history[agent].append({
            'Hora': datetime.now().strftime("%H:%M:%S"),
            'Ciclo': 0,
            'Crenças': ["sistema_iniciado", "pronto_para_comunicar"],
            'Metas': ["inicializar_sistema"]
        })
    
    logs.append("---")
    logs.append("📨 Iniciando comunicação entre agentes...")
    
    # Simula diferentes padrões de comunicação
    for cycle, sender in enumerate(agents, 1):
        # Cada agente envia mensagem para o próximo (anéis)
        receiver = agents[(cycle) % len(agents)]
        
        # Atualiza histórico do sender
        current_time = datetime.now().strftime("%H:%M:%S")
        agent_history[sender].append({
            'Hora': current_time,
            'Ciclo': cycle,
            'Crenças': [f"enviando_msg_para_{receiver}", "comunicacao_ativa"],
            'Metas': [f"enviar_mensagem_{receiver}", "manter_conexao"]
        })
        
        logs.append(f"📤 {sender} → {receiver}: Mensagem de saudação")
        
        # Pequena pausa entre ações
        time.sleep(0.1)
        
        # Atualiza histórico do receiver
        current_time = datetime.now().strftime("%H:%M:%S")
        agent_history[receiver].append({
            'Hora': current_time,
            'Ciclo': cycle,
            'Crenças': [f"recebendo_msg_de_{sender}", "mensagem_processada"],
            'Metas': [f"responder_{sender}", "processar_mensagem"]
        })
        
        logs.append(f"📥 {receiver} ← {sender}: Confirmação recebida")
        
        # Alguns agentes fazem broadcast
        if cycle == 1:
            logs.append(f"📢 {sender} faz broadcast para todos os agentes")
            # Atualiza histórico para broadcast
            current_time = datetime.now().strftime("%H:%M:%S")
            agent_history[sender].append({
                'Hora': current_time,
                'Ciclo': cycle,
                'Crenças': ["broadcast_enviado", "todos_notificados"],
                'Metas': ["coordenar_agentes", "manter_sincronizacao"]
            })
    
    # Ciclo final
    final_cycle = len(agents) + 1
    current_time = datetime.now().strftime("%H:%M:%S")
    for agent in agents:
        agent_history[agent].append({
            'Hora': current_time,
            'Ciclo': final_cycle,
            'Crenças': ["sistema_finalizado", "todas_tarefas_concluidas"],
            'Metas': ["finalizar_processos", "aguardar_nova_execucao"]
        })
    
    logs.append("---")
    logs.append("✅ Todos os agentes finalizaram suas tarefas")
    
    return logs, agent_history

def create_agent_history_table(agent_history, agent_name):
    """Cria uma tabela DataFrame para o histórico de um agente"""
    if agent_name not in agent_history or not agent_history[agent_name]:
        return pd.DataFrame()
    
    df = pd.DataFrame(agent_history[agent_name])
    return df

# Configuração da página
st.set_page_config(page_title="Simulador MAS2J", layout="wide")
st.title("🔍 Analisador de Projetos MAS2J")

# Sidebar com informações
with st.sidebar:
    st.header("📁 Projetos Disponíveis")
    st.info("Selecione um projeto da lista para analisar")

# Obtém lista de projetos
project_files = get_project_files()

# Debug: mostrar arquivos encontrados
st.sidebar.write(f"📊 Arquivos encontrados: {len(project_files)}")
for file in project_files:
    st.sidebar.write(f"• {file.name}")

if project_files:
    # Cria lista de nomes para o selectbox
    project_names = [file.name for file in project_files]
    
    # Selectbox para escolher o projeto
    selected_project = st.selectbox(
        "Selecione um projeto:",
        project_names,
        index=0
    )
    
    # Mostra informações do projeto selecionado
    st.subheader(f"📄 Projeto: {selected_project}")
    
    # Carrega e exibe o conteúdo do projeto
    project_content = load_project_file(selected_project)
    
    if project_content:
        # Abas para organizar as informações
        tab1, tab2, tab3 = st.tabs(["📋 Código", "🤖 Agentes", "🔄 Simulação"])
        
        with tab1:
            st.subheader("Conteúdo do Arquivo")
            st.code(project_content, language="java")
        
        with tab2:
            st.subheader("Agentes Identificados")
            agents = parse_mas2j(project_content)
            
            if agents:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("**Lista de Agentes:**")
                    for i, agent in enumerate(agents, 1):
                        st.write(f"{i}. `{agent}`")
                
                with col2:
                    st.write("**Estatísticas:**")
                    st.metric("Total de Agentes", len(agents))
                    
                # Debug: mostrar seção de agentes encontrada
                st.sidebar.write("🔍 Agentes encontrados:")
                for agent in agents:
                    st.sidebar.write(f"• {agent}")
            else:
                st.warning("⚠️ Nenhum agente identificado no arquivo!")
                st.info("💡 Dica: Verifique se o arquivo segue o formato .mas2j correto")
                
                # Debug adicional
                st.sidebar.subheader("🔧 Debug do Parser")
                content_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', project_content, flags=re.MULTILINE | re.DOTALL)
                agents_match = re.search(r'agents\s*:\s*(.*?)(?=\n\s*\w+\s*:|$)', content_no_comments, re.DOTALL)
                if agents_match:
                    st.sidebar.write("Seção 'agents' encontrada:")
                    st.sidebar.code(agents_match.group(1))
                else:
                    st.sidebar.write("Nenhuma seção 'agents' encontrada")
        
        with tab3:
            st.subheader("Simulação de Execução")
            agents = parse_mas2j(project_content)
            
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
                
                # Executa simulação se solicitado
                if st.session_state.get('run_simulation', False):
                    logs, agent_history = simulate_communication(agents)
                    
                    # Container para logs com rolagem
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
                    
                    # Salva o histórico na session state
                    st.session_state.agent_history = agent_history
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
                                
                                # Formata a tabela para melhor visualização
                                styled_df = history_df.style.set_properties(**{
                                    'background-color': '#f0f2f6',
                                    'color': 'black',
                                    'border-color': 'white'
                                })
                                
                                st.dataframe(styled_df, use_container_width=True)
                                
                                # Estatísticas do agente
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total de Ciclos", len(history_df))
                                with col2:
                                    total_beliefs = sum(len(beliefs) for beliefs in history_df['Crenças'])
                                    st.metric("Total de Crenças", total_beliefs)
                                with col3:
                                    total_goals = sum(len(goals) for goals in history_df['Metas'])
                                    st.metric("Total de Metas", total_goals)
                            else:
                                st.warning(f"Nenhum histórico disponível para o agente {agent}")
            else:
                st.error("❌ Não é possível simular: nenhum agente encontrado")
    
    else:
        st.error(f"❌ Erro ao carregar o arquivo: {selected_project}")

else:
    st.error("📂 Nenhum projeto encontrado na pasta './projects'")
    
    st.info("""
    **Estrutura do projeto necessária:**
    ```
    seu-repositorio/
    ├── app.py
    ├── requirements.txt
    └── projects/
        ├── Communication.mas2j
        └── outros_projetos.mas2j
    ```
    """)

# Footer
st.markdown("---")
st.caption("Desenvolvido para análise de sistemas multiagente")

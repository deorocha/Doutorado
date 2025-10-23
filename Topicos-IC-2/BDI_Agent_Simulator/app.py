import streamlit as st
import xml.etree.ElementTree as ET
import re
import os
from pathlib import Path

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
    
    # DEBUG: Mostrar conteúdo sem comentários
    st.sidebar.code(content_no_comments[:500] + "..." if len(content_no_comments) > 500 else content_no_comments, language="java")
    
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
    """Simula a comunicação entre agentes"""
    logs = []
    
    if not agents:
        logs.append("⚠️ Nenhum agente encontrado para simular comunicação")
        return logs
    
    logs.append("🚀 Iniciando sistema multiagente...")
    
    for agent in agents:
        logs.append(f"✅ {agent} inicializado")
    
    logs.append("---")
    logs.append("📨 Iniciando comunicação entre agentes...")
    
    # Simula diferentes padrões de comunicação
    for i, sender in enumerate(agents):
        # Cada agente envia mensagem para o próximo (anéis)
        receiver = agents[(i + 1) % len(agents)]
        logs.append(f"📤 {sender} → {receiver}: Mensagem de saudação")
        logs.append(f"📥 {receiver} ← {sender}: Confirmação recebida")
        
        # Alguns agentes fazem broadcast
        if i == 0:
            logs.append(f"📢 {sender} faz broadcast para todos os agentes")
    
    logs.append("---")
    logs.append("✅ Todos os agentes finalizaram suas tarefas")
    
    return logs

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
                
                # Executa simulação se solicitado
                if st.session_state.get('run_simulation', False):
                    logs = simulate_communication(agents)
                    
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
                            import time
                            time.sleep(delay_map[simulation_speed])
                            
                            # Atualiza display
                            log_text = "\n".join(current_logs)
                            log_display.code(log_text)
                    
                    st.session_state.run_simulation = False
                    st.success("🎉 Simulação concluída!")
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

import streamlit as st
import xml.etree.ElementTree as ET
import re
import os
from pathlib import Path

def get_project_files():
    """Obtém a lista de arquivos .mas2j da pasta projects"""
    project_dir = Path("./projects")
    if project_dir.exists():
        mas2j_files = list(project_dir.glob("*.mas2j"))
        mas3j_files = list(project_dir.glob("*.mas3j"))
        return mas2j_files + mas3j_files
    return []

def load_project_file(filename):
    """Carrega o conteúdo de um arquivo de projeto"""
    project_path = Path("./projects") / filename
    if project_path.exists():
        with open(project_path, 'r', encoding='utf-8') as file:
            return file.read()
    return None

def parse_mas2j(file_content):
    """Faz o parsing básico de um arquivo .mas2j para extrair agentes"""
    agents = []
    
    # Remove comentários para facilitar o parsing
    content_no_comments = re.sub(r'//.*?$|/\*.*?\*/', '', file_content, flags=re.MULTILINE | re.DOTALL)
    
    # Padrão para encontrar definições de agentes
    agent_pattern = r'agent\s*:\s*(\w+)\s*\{'
    agents.extend(re.findall(agent_pattern, content_no_comments))
    
    # Padrão alternativo para agentes em linhas individuais
    alt_pattern = r'agents?\s*:\s*((?:\w+\s*)+);'
    alt_match = re.search(alt_pattern, content_no_comments)
    if alt_match:
        agents.extend(re.findall(r'\w+', alt_match.group(1)))
    
    # Padrão para agentes entre chaves
    brace_pattern = r'agents?\s*:\s*\{([^}]+)\}'
    brace_match = re.search(brace_pattern, content_no_comments)
    if brace_match:
        agents.extend(re.findall(r'\w+', brace_match.group(1)))
    
    return list(set(agents))  # Remove duplicatas

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
            else:
                st.warning("⚠️ Nenhum agente identificado no arquivo!")
                st.info("💡 Dica: Verifique se o arquivo segue o formato .mas2j correto")
        
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
    **Como adicionar projetos:**
    
    1. Crie uma pasta chamada `projects` no mesmo diretório do app
    2. Adicione arquivos `.mas2j` ou `.mas3j` nesta pasta
    3. Estruture seu repositório assim:
    ```
    seu-repositorio/
    ├── app.py
    ├── requirements.txt
    └── projects/
        ├── projeto1.mas2j
        ├── projeto2.mas2j
        └── projeto3.mas3j
    ```
    """)

# Footer
st.markdown("---")
st.caption("Desenvolvido para análise de sistemas multiagente | 💡 Dica: Verifique se a pasta 'projects' existe e contém arquivos .mas2j")

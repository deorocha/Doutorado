import streamlit as st
import xml.etree.ElementTree as ET
import re
import os

def parse_mas2j(file_content):
    """Faz o parsing básico de um arquivo .mas2j para extrair agentes"""
    agents = []
    
    # Padrão para encontrar definições de agentes
    agent_pattern = r'agent\s*:\s*(\w+)\s*\{'
    agents.extend(re.findall(agent_pattern, file_content))
    
    # Padrão alternativo para agentes em linhas individuais
    alt_pattern = r'agents?\s*:\s*((?:\w+\s*)+);'
    alt_match = re.search(alt_pattern, file_content)
    if alt_match:
        agents.extend(alt_match.group(1).split())
    
    return list(set(agents))  # Remove duplicatas

def simulate_communication(agents):
    """Simula a comunicação entre agentes"""
    logs = []
    for i, agent in enumerate(agents):
        logs.append(f"{agent} inicializado")
        
        # Simula envio de mensagens
        if i < len(agents) - 1:
            logs.append(f"{agent} → {agents[i+1]}: Olá Agente {agents[i+1]}!")
        if i > 0:
            logs.append(f"{agent} ← {agents[i-1]}: Mensagem recebida")
            
        logs.append(f"{agent} processando tarefa...")
        logs.append("---")
    return logs

st.set_page_config(page_title="Simulador MAS2J", layout="wide")
st.title("🔍 Analisador de Projetos MAS2J")

uploaded_file = st.file_uploader("Carregue seu arquivo .mas2j", type=["mas2j"])

if uploaded_file:
    content = uploaded_file.read().decode()
    
    st.subheader("📄 Conteúdo do Arquivo")
    st.code(content)
    
    agents = parse_mas2j(content)
    
    st.subheader("🤖 Agentes Identificados")
    if agents:
        st.write(", ".join(agents))
        
        st.subheader("🔄 Simulação de Execução")
        logs = simulate_communication(agents)
        
        for log in logs:
            if "→" in log:
                st.success(log)
            elif "←" in log:
                st.info(log)
            elif "processando" in log:
                st.warning(log)
            elif "inicializado" in log:
                st.error(log)
            else:
                st.write(log)
                
    else:
        st.warning("Nenhum agente identificado no arquivo!")

else:
    st.info("👆 Por favor, carregue um arquivo .mas2j para começar")

st.markdown("---")
st.caption("Desenvolvido para demonstração de sistemas multiagente")

# app.py - Chatbot MEWS com modelo treinado
import streamlit as st
import json
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Chatbot MEWS-LLM", 
    page_icon="🤖",
    layout="wide"
)

# Título principal
st.title("🤖 ChatBot MEWS-LLM Especializado")
st.markdown("Consulta informações detalhadas sobre procedimentos hospitalares")

# Definir o caminho base do projeto
PROJECT_ROOT = Path(__file__).parent

# Importa o chatbot
try:
    from mews_chatbot import MEWSChatbot
except ImportError as e:
    st.error(f"❌ Erro ao importar módulos: {e}")
    st.stop()

# Inicializa o chatbot
@st.cache_resource
def init_chatbot():
    chatbot = MEWSChatbot()
    model_loaded = chatbot.load_model()
    
    if not model_loaded:
        st.warning("⚠️ Modelo IA não carregado. Execute train_model.py primeiro.")
    
    return chatbot

chatbot = init_chatbot()

def main():
    # Sidebar
    with st.sidebar:
        st.title("🏥 Sistema MEWS")
        st.markdown("---")
        st.markdown("""
        **Faixas MEWS:**
        - 🟢 Verde - Monitoramento
        - 🟡 Amarelo - Ações Imediatas  
        - 🔴 Vermelho - Emergência
        """)
        
        st.markdown("---")
        st.subheader("Configurações")
        
        model_info = chatbot.get_model_info()
        if model_info["modelo_carregado"]:
            st.success(f"✅ Modelo IA Carregado")
            st.info(f"📚 {model_info['documentos_carregados']} procedimentos")
        else:
            st.error("❌ Modelo não carregado")
        
        if st.button("🗑️ Limpar Conversa"):
            if 'conversation' in st.session_state:
                st.session_state.conversation = []
            st.rerun()

    # Inicializa conversa
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []
    
    # Exibe histórico
    for message in st.session_state.conversation:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Input do chat
    if prompt := st.chat_input("Digite sua pergunta sobre procedimentos MEWS..."):
        # Adiciona mensagem do usuário
        st.session_state.conversation.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Busca e mostra resposta
        with st.chat_message("assistant"):
            with st.spinner("🔍 Buscando resposta..."):
                if chatbot.model:
                    response = chatbot.get_answer(prompt)
                else:
                    response = "❌ Modelo não carregado. Execute train_model.py primeiro."
            
            st.markdown(response)
            st.session_state.conversation.append({"role": "assistant", "content": response})
    
    # Mensagem de boas-vindas
    if not st.session_state.conversation:
        with st.chat_message("assistant"):
            st.markdown("""
👋 **Olá! Sou seu assistente especializado em procedimentos MEWS.**

**💡 Exemplos de perguntas:**
- "Por que devo verificar sinais vitais regularmente?"
- "Qual o fundamento da monitorização respiratória?"
- "Quais os riscos de não comunicar alterações ao médico?"
- "Por que é importante orientar pacientes?"

**📝 Formato das respostas:**
Fundamento Fisiológico: [explicação]
Riscos da Omissão: [consequências]
Evidências Clínicas: [comprovações]
Impacto no Paciente: [efeitos]

**Digite sua pergunta abaixo!**
""")

if __name__ == "__main__":
    main()

# app.py - Chatbot MEWS com modelo treinado - COMPATÍVEL COM STREAMLIT CLOUD
import streamlit as st
import json
from pathlib import Path
import sys

# Configuração da página
st.set_page_config(
    page_title="Chatbot MEWS-LLM", 
    page_icon="🤖",
    layout="wide"
)

# Título principal
st.title("🤖 ChatBot MEWS-LLM")
st.markdown("Consulta informações detalhadas sobre procedimentos hospitalares com **respostas estruturadas**")

# Definir o caminho base do projeto
PROJECT_ROOT = Path(__file__).parent

# Carrega o arquivo CSS (se existir)
css_path = PROJECT_ROOT / "styles" / "styles.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

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
    
    # Debug: verificar estrutura de diretórios
    st.sidebar.write("🔍 Debug - Estrutura de diretórios:")
    st.sidebar.write(f"Diretório atual: {Path.cwd()}")
    st.sidebar.write(f"Diretório do app: {PROJECT_ROOT}")
    
    # Verificar se a pasta models existe
    models_dir = PROJECT_ROOT / "models"
    st.sidebar.write(f"Pasta models existe: {models_dir.exists()}")
    
    if models_dir.exists():
        files = list(models_dir.glob("*"))
        st.sidebar.write(f"Arquivos em models: {[f.name for f in files]}")
    
    # Tenta carregar o modelo
    model_loaded = chatbot.load_model()
    
    if not model_loaded:
        st.error("""
        ❌ **Modelo IA não carregado no Streamlit Cloud**
        
        **Possíveis soluções:**
        1. Verifique se a pasta `models/` está no GitHub
        2. Verifique se `mews_model.pkl` e `mews_model.pkl_transformer/` estão na pasta models
        3. Os arquivos de modelo podem ser muito grandes para o GitHub
        4. Execute `train_model.py` localmente e faça commit dos arquivos do modelo
        """)
    
    return chatbot

chatbot = init_chatbot()

# ... o resto do código permanece igual ...
def find_procedure_fallback(json_data, query):
    """Busca básica fallback caso o modelo não esteja disponível"""
    query_lower = query.lower().strip()
    
    for faixa in json_data.get("faixas_mews", []):
        for ator in faixa.get("atores", []):
            for conduta in ator.get("condutas", []):
                for procedimento in conduta.get("procedimentos", []):
                    proc_text = procedimento.get("procedimento", "").lower()
                    if query_lower in proc_text:
                        return {
                            "procedimento": procedimento.get("procedimento", ""),
                            "motivos": procedimento.get("motivos", {}),
                            "faixa": faixa.get("nome", ""),
                            "ator": ator.get("ator", ""),
                            "conduta": conduta.get("conduta", "")
                        }
    return None

def format_fallback_response(result):
    """Formata resposta no modo fallback"""
    if not result:
        return "❌ **Este assunto não faz parte da minha base de dados**"
    
    motivos = result.get('motivos', {})
    response = ""
    
    # Fundamento Fisiológico
    if motivos.get('fundamento'):
        response += f"**Fundamento Fisiológico:** {motivos['fundamento']}\n\n"
    
    # Riscos da Omissão
    if motivos.get('riscos'):
        response += f"**Riscos da Omissão:** {motivos['riscos']}\n\n"
    
    # Evidências Clínicas
    if motivos.get('evidencias'):
        response += f"**Evidências Clínicas:** {motivos['evidencias']}\n\n"
    
    # Impacto no Paciente
    if motivos.get('impacto'):
        response += f"**Impacto no Paciente:** {motivos['impacto']}\n\n"
    
    # Se não encontrou nenhum motivo, retorna mensagem básica
    if not response:
        response = f"**Procedimento encontrado:** {result.get('procedimento', '')}\n"
        response += f"**Faixa MEWS:** {result.get('faixa', '')} | **Responsável:** {result.get('ator', '')}\n"
        response += f"**Conduta:** {result.get('conduta', '')}\n\n"
        response += "ℹ️ *Informações detalhadas não disponíveis para este procedimento*"
    
    return response

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
        st.subheader("🤖 Status do Modelo")
        
        model_info = chatbot.get_model_info()
        if model_info["modelo_carregado"]:
            st.success(f"✅ Modelo IA Carregado")
            st.info(f"📚 {model_info['documentos_carregados']} procedimentos")
            
            # Controle de sensibilidade
            threshold = st.slider(
                "Precisão da Busca",
                min_value=0.3,
                max_value=0.7,
                value=chatbot.similarity_threshold,
                step=0.05,
                help="Ajuste quão precisa deve ser a correspondência"
            )
            chatbot.set_similarity_threshold(threshold)
        else:
            st.warning("⚠️ Modo Básico")
            st.info("Execute train_model.py para ativar a IA")
        
        st.markdown("---")
        
        if st.button("🗑️ Limpar Conversa", use_container_width=True, type="secondary"):
            if 'conversation' in st.session_state:
                st.session_state.conversation = []
            st.rerun()
        
        # Carregar JSON para fallback
        json_path = PROJECT_ROOT / "arquivos" / "procedimentos.json"
        json_data = {}
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                st.success("✅ Base de dados carregada")
            except Exception as e:
                st.error(f"❌ Erro ao carregar JSON: {e}")
        else:
            st.error("❌ Arquivo procedimentos.json não encontrado")

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
            with st.spinner("🔍 Analisando sua pergunta..."):
                if chatbot.model and chatbot.embeddings is not None:
                    # Usa o modelo treinado
                    response = chatbot.get_answer(prompt)
                else:
                    # Fallback para busca básica
                    st.warning("⚡ Modo básico - usando busca por palavras-chave")
                    result = find_procedure_fallback(json_data, prompt)
                    response = format_fallback_response(result)
            
            st.markdown(response)
            st.session_state.conversation.append({"role": "assistant", "content": response})
    
    # Mensagem de boas-vindas
    if not st.session_state.conversation:
        with st.chat_message("assistant"):
            st.markdown("""
👋 **Olá! Sou seu assistente especializado em procedimentos MEWS.**

**🎯 Como funciono:**
- Forneço respostas **estruturadas** com base científica
- Apresento informações em **4 categorias** específicas:
  1. **Fundamento Fisiológico** - Base científica do procedimento
  2. **Riscos da Omissão** - Consequências de não realizar o procedimento  
  3. **Evidências Clínicas** - Comprovações baseadas em estudos
  4. **Impacto no Paciente** - Efeitos diretos no bem-estar

**💡 Exemplos de perguntas:**
- "Por que devo verificar sinais vitais regularmente?"
- "Qual o fundamento fisiológico da monitorização respiratória?"
- "Quais os riscos de não comunicar alterações ao médico?"
- "Por que é importante orientar pacientes sobre sinais de alerta?"
- "Qual o impacto da documentação no prontuário?"

**📝 Formato das respostas:**
Fundamento Fisiológico: [explicação científica]
Riscos da Omissão: [consequências]
Evidências Clínicas: [comprovações]
Impacto no Paciente: [efeitos]

**Digite sua pergunta abaixo!**
""")

if __name__ == "__main__":
    main()


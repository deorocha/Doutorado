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
    
    # Verificar se a pasta models existe
    models_dir = PROJECT_ROOT / "models"
    
    # Verificação mais robusta dos arquivos do modelo
    model_loaded = False
    model_files_exist = False
    
    if models_dir.exists():
        # Verifica arquivos específicos
        pkl_file = models_dir / "mews_model.pkl"
        transformer_dir = models_dir / "mews_model.pkl_transformer"
        
        pkl_exists = pkl_file.exists() and pkl_file.is_file()
        transformer_exists = transformer_dir.exists() and transformer_dir.is_dir()
        
        model_files_exist = pkl_exists and transformer_exists
        
        # Debug silencioso - não mostra na UI
        print(f"Model files check - PKL: {pkl_exists}, Transformer: {transformer_exists}")
    
    # Tenta carregar o modelo apenas se os arquivos existirem
    if model_files_exist:
        try:
            model_loaded = chatbot.load_model()
            if model_loaded:
                print("✅ Modelo carregado com sucesso")
            else:
                print("❌ Falha ao carregar modelo (load_model retornou False)")
        except Exception as e:
            print(f"❌ Exceção ao carregar modelo: {e}")
            model_loaded = False
    else:
        print("❌ Arquivos do modelo não encontrados")
        model_loaded = False
    
    # Se não conseguiu carregar, mostra mensagem de erro
    if not model_loaded:
        # Verifica quais arquivos estão faltando para mensagem mais específica
        missing_files = []
        models_dir = PROJECT_ROOT / "models"
        
        if not models_dir.exists():
            missing_files.append("pasta 'models/'")
        else:
            if not (models_dir / "mews_model.pkl").exists():
                missing_files.append("arquivo 'mews_model.pkl'")
            if not (models_dir / "mews_model.pkl_transformer").exists():
                missing_files.append("pasta 'mews_model.pkl_transformer/'")
        
        if missing_files:
            missing_text = ", ".join(missing_files)
            st.error(f"""
            ❌ **Modelo IA não carregado - Arquivos faltando: {missing_text}**
            
            **Soluções:**
            1. Verifique se a pasta `models/` está no repositório do GitHub
            2. Certifique-se de que `mews_model.pkl` e `mews_model.pkl_transformer/` estão na pasta models
            3. Os arquivos de modelo podem ser muito grandes (>25MB) para o Git
               - Use Git LFS (Large File Storage) para arquivos grandes
               - Ou reduza o tamanho do modelo no train_model.py
            4. Execute `train_model.py` localmente e faça commit dos arquivos do modelo
            5. Verifique se fez push de todos os arquivos para o GitHub
            """)
        else:
            st.error("""
            ❌ **Modelo IA não carregado - Erro desconhecido**
            
            **Soluções:**
            1. Execute `train_model.py` localmente para gerar os arquivos do modelo
            2. Verifique se todos os arquivos estão commitados e push para o GitHub
            3. Verifique os logs de erro no Streamlit Cloud
            """)
    
    return chatbot

chatbot = init_chatbot()

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
        st.markdown("""
        **Faixas MEWS:**
        - 🟢 Verde - Monitoramento
        - 🟡 Amarelo - Ações Imediatas  
        - 🔴 Vermelho - Emergência
        """)
        
        model_info = chatbot.get_model_info()
        if model_info["modelo_carregado"]:
            # Controle de sensibilidade
            threshold = st.slider(
                "Precisão da Busca",
                min_value=0.3,
                max_value=0.7,
                # value=chatbot.similarity_threshold,
                value=0.45,
                step=0.01,
                help="Ajuste quão precisa deve ser a correspondência"
            )
            chatbot.set_similarity_threshold(threshold)
            # st.success("✅ Modo IA Ativo")
        else:
            st.warning("⚠️ Modo Básico")
            st.info("Usando busca por palavras-chave")
        
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

        with st.expander("🎯 Como funciono", expanded=False):
            st.markdown("""
            <style>
            .small-font {
                font-size:14px;
            }
            </style>
            <div class="small-font">
                🎯 Como funciono:<p>
                - Forneço respostas estruturadas com base científica;<br>
                - Apresento informações em 4 categorias específicas:
                <ul>
                    <li>  1. Fundamento Fisiológico - Base científica do procedimento;<br></li>
                    <li>  2. Riscos da Omissão - Consequências de não realizar o procedimento;<br></li>
                    <li>  3. Evidências Clínicas - Comprovações baseadas em estudos;<br></li>
                    <li>  4. Impacto no Paciente - Efeitos diretos no bem-estar.<p></li>
                </ul>
                💡 Exemplos de perguntas:
                <ul>
                    <li>  - "Por que devo verificar sinais vitais regularmente?"<br></li>
                    <li>  - "Qual o fundamento fisiológico da monitorização respiratória?"<br></li>
                    <li>  - "Quais os riscos de não comunicar alterações ao médico?"<br></li>
                    <li>  - "Por que é importante orientar pacientes sobre sinais de alerta?"<br></li>
                    <li>  - "Qual o impacto da documentação no prontuário?"<br></li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

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
                model_info = chatbot.get_model_info()
                if model_info["modelo_carregado"]:
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

**Estou aqui para ajudar você a entender:** 
- 📊 **Fundamentos fisiológicos** dos procedimentos
- ⚠️ **Riscos da omissão** de cuidados
- 🔬 **Evidências clínicas** que embasam as condutas
- 💡 **Impacto direto** no bem-estar do paciente

**Como posso ajudar você hoje?** 
*Exemplo: "Por que é importante monitorar os sinais vitais regularmente?"*
""")

if __name__ == "__main__":
    main()






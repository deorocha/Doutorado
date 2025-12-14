# app_streamlit_corrigido.py - VERSÃO CORRIGIDA

import streamlit as st
import torch
import os
import json
from datetime import datetime
from pathlib import Path
import sys

# Adicionar diretório atual ao path para importar módulos locais
sys.path.append('.')

# Configuração da página
st.set_page_config(
    page_title="Gerador de Texto com LLM Finetunado",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #374151;
        font-weight: 600;
        margin-top: 1.5rem;
    }
    .generated-text {
        background-color: #F3F4F6;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #3B82F6;
        font-size: 1.1rem;
        line-height: 1.6;
        margin-top: 1rem;
    }
    .stButton button {
        width: 100%;
        border-radius: 8px;
        padding: 0.75rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Importar o carregador de modelo
try:
    from model_loader import LLMModelLoader
except ImportError:
    st.error("❌ Módulo 'model_loader' não encontrado")
    st.stop()

# Inicializar estados da sessão
def init_session_state():
    """Inicializa todos os estados da sessão"""
    if 'model_loader' not in st.session_state:
        st.session_state.model_loader = None
    if 'model_loaded' not in st.session_state:
        st.session_state.model_loaded = False
    if 'generated_text' not in st.session_state:
        st.session_state.generated_text = ""
    if 'generation_params' not in st.session_state:
        st.session_state.generation_params = {}
    if 'generation_history' not in st.session_state:
        st.session_state.generation_history = []
    if 'model_path' not in st.session_state:
        st.session_state.model_path = "./fine_tuned_model"

# Inicializar
init_session_state()

def load_model(model_path):
    """Carrega o modelo finetunado"""
    try:
        with st.spinner("🔍 Carregando modelo..."):
            # Verificar se o caminho existe
            if not os.path.exists(model_path):
                st.error(f"❌ Caminho não encontrado: {model_path}")
                return False
            
            # Criar e carregar o modelo
            model_loader = LLMModelLoader(model_path)
            success = model_loader.load_model()
            
            if success:
                # Armazenar no session_state
                st.session_state.model_loader = model_loader
                st.session_state.model_loaded = True
                st.session_state.model_path = model_path
                st.success("✅ Modelo carregado com sucesso!")
                return True
            else:
                st.error("❌ Falha ao carregar o modelo")
                return False
    except Exception as e:
        st.error(f"❌ Erro ao carregar modelo: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def generate_text(prompt, params):
    """Gera texto com os parâmetros fornecidos"""
    try:
        if not st.session_state.model_loaded or st.session_state.model_loader is None:
            st.warning("⚠️ Carregue um modelo primeiro!")
            return None
        
        with st.spinner("✨ Gerando texto..."):
            # Converter palavras para tokens (aproximadamente)
            max_tokens = int(params['max_words'] * 1.5)  # Aproximação
            
            generated_text = st.session_state.model_loader.generate(
                prompt=prompt,
                max_length=max_tokens,
                temperature=params['temperature'],
                top_p=params['top_p'],
                repetition_penalty=params['repetition_penalty']
            )
            
            return generated_text
    except Exception as e:
        st.error(f"❌ Erro na geração: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def save_generation(prompt, text, params):
    """Salva a geração em arquivo"""
    try:
        # Criar diretório se não existir
        output_dir = Path("generated_texts")
        output_dir.mkdir(exist_ok=True)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"gerado_{timestamp}.txt"
        
        # Salvar texto
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Prompt: {prompt}\n")
            f.write(f"Temperatura: {params['temperature']}\n")
            f.write(f"Top-p: {params['top_p']}\n")
            f.write(f"Palavras máx: {params['max_words']}\n")
            f.write(f"Penalidade repetição: {params['repetition_penalty']}\n")
            f.write("-" * 50 + "\n")
            f.write(text + "\n")
        
        return str(filename)
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {str(e)}")
        return None

# Cabeçalho
st.markdown('<h1 class="main-header">🤖 Gerador de Texto com LLM Finetunado</h1>', 
           unsafe_allow_html=True)
st.markdown("Gere textos criativos usando modelos de linguagem treinados em português")

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Configurações do Modelo")
    
    # Seletor de modelo
    model_path = st.text_input(
        "📁 Caminho do Modelo",
        value=st.session_state.model_path,
        help="Caminho para a pasta do modelo finetunado"
    )
    
    # Botão para carregar modelo
    if st.button("🚀 Carregar Modelo", type="primary", use_container_width=True):
        if model_path != st.session_state.model_path or not st.session_state.model_loaded:
            load_model(model_path)
        else:
            st.info("ℹ️ Modelo já está carregado")
    
    # Botão para descarregar modelo
    if st.session_state.model_loaded:
        if st.button("🗑️ Descarregar Modelo", type="secondary", use_container_width=True):
            st.session_state.model_loader = None
            st.session_state.model_loaded = False
            st.rerun()
    
    st.divider()
    
    st.markdown("### 📝 Parâmetros de Geração")
    
    # Parâmetros de geração com valores padrão
    temperature = st.slider(
        "🌡️ Temperatura",
        min_value=0.1,
        max_value=1.5,
        value=0.8,
        step=0.1,
        help="Controla a aleatoriedade (maior = mais criativo)"
    )
    
    top_p = st.slider(
        "🎯 Top-p (nucleus sampling)",
        min_value=0.1,
        max_value=1.0,
        value=0.9,
        step=0.05,
        help="Controla a diversidade das palavras escolhidas"
    )
    
    max_words = st.number_input(
        "📏 Máximo de Palavras",
        min_value=10,
        max_value=1000,
        value=100,
        step=10,
        help="Número máximo aproximado de palavras a gerar"
    )
    
    repetition_penalty = st.slider(
        "🔁 Penalidade de Repetição",
        min_value=1.0,
        max_value=2.0,
        value=1.2,
        step=0.1,
        help="Evita repetição de palavras (maior = menos repetição)"
    )
    
    st.divider()
    
    # Informações do sistema
    st.markdown("### 💻 Sistema")
    st.write(f"PyTorch: {torch.__version__}")
    device = "GPU 🚀" if torch.cuda.is_available() else "CPU ⚡"
    st.write(f"Dispositivo: {device}")
    
    if st.session_state.model_loaded and st.session_state.model_loader:
        st.success("✅ Modelo carregado")
        vocab_size = st.session_state.model_loader.get_vocab_size()
        if vocab_size:
            st.write(f"Vocabulário: {vocab_size:,} tokens")
    
    st.divider()
    
    # Links úteis
    st.markdown("### 📚 Ajuda")
    with st.expander("💡 Dicas de uso"):
        st.markdown("""
        - **Prompt inicial**: Use frases completas para melhores resultados
        - **Temperatura**: 0.7-0.9 para textos criativos, 0.3-0.6 para mais focados
        - **Top-p**: 0.9-0.95 para equilíbrio entre criatividade e coerência
        - **Palavras**: 50-150 palavras geralmente produz textos bem estruturados
        """)

# Área principal
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown('<h2 class="sub-header">📝 Entrada de Texto</h2>', 
               unsafe_allow_html=True)
    
    # Prompt de entrada
    prompt = st.text_area(
        "Digite o início do texto (prompt):",
        value="A inteligência artificial tem revolucionado",
        height=150,
        help="O texto que servirá como base para a geração",
        key="prompt_input"
    )
    
    # Botões de ação
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        generate_btn = st.button("✨ Gerar Texto", type="primary", 
                                use_container_width=True, key="generate_btn")
    
    with col_btn2:
        clear_btn = st.button("🗑️ Limpar", use_container_width=True, key="clear_btn")
    
    with col_btn3:
        save_disabled = not st.session_state.generated_text
        save_btn = st.button("💾 Salvar", disabled=save_disabled, 
                            use_container_width=True, key="save_btn")

with col2:
    st.markdown('<h2 class="sub-header">📊 Estatísticas</h2>', 
               unsafe_allow_html=True)
    
    if st.session_state.generated_text:
        text = st.session_state.generated_text
        
        # Calcular estatísticas
        word_count = len(text.split())
        char_count = len(text)
        sentence_count = text.count('.') + text.count('!') + text.count('?')
        
        # Exibir métricas
        st.metric("📝 Palavras", word_count)
        st.metric("🔤 Caracteres", char_count)
        st.metric("📚 Sentenças", sentence_count)
        
        # Mostrar parâmetros usados
        with st.expander("⚙️ Parâmetros usados"):
            if st.session_state.generation_params:
                params = st.session_state.generation_params
                st.write(f"🌡️ Temperatura: {params.get('temperature', 'N/A')}")
                st.write(f"🎯 Top-p: {params.get('top_p', 'N/A')}")
                st.write(f"📏 Palavras máx: {params.get('max_words', 'N/A')}")

# Processar ações dos botões
if generate_btn:
    if not st.session_state.model_loaded:
        st.warning("⚠️ Carregue um modelo primeiro na barra lateral!")
    else:
        # Parâmetros de geração
        params = {
            'temperature': temperature,
            'top_p': top_p,
            'max_words': max_words,
            'repetition_penalty': repetition_penalty
        }
        
        # Gerar texto
        generated_text = generate_text(prompt, params)
        
        if generated_text:
            st.session_state.generated_text = generated_text
            st.session_state.generation_params = params
            
            # Adicionar ao histórico
            st.session_state.generation_history.append({
                'timestamp': datetime.now(),
                'prompt': prompt,
                'text': generated_text[:100] + "..." if len(generated_text) > 100 else generated_text
            })
            
            # Forçar rerun para atualizar a interface
            st.rerun()

# Limpar texto
if clear_btn:
    st.session_state.generated_text = ""
    st.rerun()

# Salvar texto
if save_btn and st.session_state.generated_text:
    filename = save_generation(
        prompt,
        st.session_state.generated_text,
        st.session_state.generation_params
    )
    if filename:
        st.success(f"✅ Texto salvo em: {filename}")

# Área de exibição do texto gerado
st.markdown('<h2 class="sub-header">📄 Texto Gerado</h2>', 
           unsafe_allow_html=True)

if st.session_state.generated_text:
    # Container com o texto gerado
    st.markdown(f'<div class="generated-text">{st.session_state.generated_text}</div>', 
               unsafe_allow_html=True)
    
    # Botões de ação para o texto gerado
    col_copy, col_download, col_refine = st.columns(3)
    
    with col_copy:
        if st.button("📋 Copiar texto", key="copy_btn"):
            st.code(st.session_state.generated_text)
            st.success("Texto copiado! (Use Ctrl+C)")
    
    with col_download:
        # Botão para download
        from io import StringIO
        text_io = StringIO(st.session_state.generated_text)
        st.download_button(
            label="⬇️ Baixar Texto",
            data=text_io.getvalue(),
            file_name=f"texto_gerado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            key="download_btn"
        )
    
    with col_refine:
        if st.button("🎨 Usar como novo prompt", key="refine_btn"):
            # Usar o texto gerado como novo prompt
            st.session_state.generated_text = ""
            st.rerun()

else:
    # Mensagem inicial
    if not st.session_state.model_loaded:
        st.info("👈 **Primeiro, carregue um modelo na barra lateral**")
    else:
        st.info("✍️ **Digite um prompt acima e clique em 'Gerar Texto'**")
    
    # Exemplos de prompts
    with st.expander("💡 Exemplos de prompts para testar"):
        st.markdown("""
        **Inteligência Artificial:**
        - `A inteligência artificial tem revolucionado`
        - `Os avanços na computação quântica`
        
        **Tecnologias:**
        - `Um framework de rastreamento corporal`
        - `A aprendizagem adaptativa utiliza algoritmos para`
        - `o Aprendizado por Reforço`
        - `as mídias sociais ganharam importância`
        """)

# Histórico de gerações (se houver)
if st.session_state.generation_history:
    st.divider()
    st.markdown('<h3 class="sub-header">📜 Histórico de Gerações</h3>', 
               unsafe_allow_html=True)
    
    # Mostrar as últimas 5 gerações
    for i, item in enumerate(reversed(st.session_state.generation_history[-5:])):
        with st.expander(f"Geração {len(st.session_state.generation_history)-i}: {item['prompt'][:50]}..."):
            st.write(f"**Prompt:** {item['prompt']}")
            st.write(f"**Texto:** {item['text']}")
            st.write(f"**Horário:** {item['timestamp'].strftime('%H:%M:%S')}")
            
            # Botão para reutilizar
            if st.button(f"🔄 Reutilizar este prompt", 
                        key=f"reuse_{i}"):
                st.session_state.generated_text = ""
                # Não é possível alterar diretamente o text_area, mas podemos mostrar uma mensagem
                st.info(f"Prompt copiado: {item['prompt'][:50]}...")

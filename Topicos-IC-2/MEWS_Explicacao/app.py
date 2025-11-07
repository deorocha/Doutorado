# EXPLICAÇÃO MEWS

import streamlit as st
import json
import os
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Explicação dos Procedimentos MEWS",
    page_icon="🧑‍🏫",
    layout="wide"
)

# Título principal
st.title("🧑‍🏫 Explicação dos Procedimentos MEWS")

# Conteúdo principal
st.markdown("Consulta informações sobre procedimentos hospitalares baseados no protocolo MEWS - Algorítimo determinístico")

# Definições das faixas MEWS
faixa_explanations = {
    "1": {
        "titulo": "BAIXO RISCO - Monitoração Preventiva",
        "contexto": "Paciente estável com parâmetros dentro da normalidade ou desvios mínimos",
        "objetivo": "Manter estabilidade e detectar precocemente qualquer mudança no estado clínico"
    },
    "2": {
        "titulo": "RISCO MODERADO - Vigilância Ativa", 
        "contexto": "Sinais precoces de deterioração com sistema fisiológico em compensação",
        "objetivo": "Interrompre a progressão da deterioração e prevenir complicações"
    },
    "3": {
        "titulo": "ALTO RISCO - Intervenção Imediata",
        "contexto": "Deterioração clínica significativa com risco iminente de falência orgânica",
        "objetivo": "Estabilizar funções vitais e prevenir morte ou lesão permanente"
    }
}

# Definir o caminho base do projeto
PROJECT_ROOT = Path(__file__).parent

# Carrega o arquivo CSS
css_path = PROJECT_ROOT / "styles" / "styles.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    st.error(f"Arquivo CSS não encontrado em: {css_path}")

# Carrega o arquivo JSON
json_path = PROJECT_ROOT / "arquivos" / "procedimentos.json"
if json_path.exists():
    with open(json_path, 'r', encoding='utf-8') as f:
        dados_json = json.load(f)
else:
    st.error(f"Arquivo JSON não encontrado em: {json_path}")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuração da Consulta")
    
    # Slider para escore MEWS
    escore_mews = st.slider("Escore MEWS", 0, 15, 0)
    
    # Calcular faixa MEWS
    if escore_mews <= 2:
        faixa_id = 1
        faixa_nome = "Verde"
    elif escore_mews <= 4:
        faixa_id = 2
        faixa_nome = "Amarelo"
    else:
        faixa_id = 3
        faixa_nome = "Vermelho"
    
    # Obter explicações da faixa
    faixa_info = faixa_explanations[str(faixa_id)]

    if faixa_id == 1:
        st.markdown(f'<div class="classification-box">{faixa_info["titulo"]}</div>', unsafe_allow_html=True)
    elif faixa_id == 2:
        st.markdown(f'<div class="classification-box-amarelo">{faixa_info["titulo"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="classification-box-vermelho">{faixa_info["titulo"]}</div>', unsafe_allow_html=True)
        
    # Encontrar dados da faixa atual
    faixa_atual = next((faixa for faixa in dados_json['faixas_mews'] if faixa['id'] == faixa_id), None)
    
    if faixa_atual:
        st.header("Procedimentos")
        
        # Criar tabs para Enfermagem e Médicos
        tab1, tab2 = st.tabs(["👩‍⚕️ Enfermagem", "👨🏻‍⚕️ Médicos"])
        
        with tab1:
            enfermagem = next((ator for ator in faixa_atual['atores'] if ator['ator'] == "ENFERMAGEM"), None)
            if enfermagem:
                for conduta in enfermagem['condutas']:
                    st.subheader(conduta['conduta'])
                    for procedimento in conduta['procedimentos']:
                        is_selected = (
                            'procedimento_selecionado' in st.session_state and
                            st.session_state.procedimento_selecionado['procedimento']['procedimento'] == procedimento['procedimento'] and
                            st.session_state.procedimento_selecionado['tipo'] == 'ENFERMAGEM'
                        )
                        
                        if st.button(
                            f"• {procedimento['procedimento']}",
                            key=f"enfermagem_{hash(procedimento['procedimento'])}",
                            use_container_width=True,
                            type="secondary" if not is_selected else "primary"
                        ):
                            st.session_state.procedimento_selecionado = {
                                'tipo': 'ENFERMAGEM',
                                'procedimento': procedimento,
                                'faixa_info': faixa_info,
                                'faixa_nome': faixa_nome,
                                'faixa_id': faixa_id
                            }
                            st.rerun()

        with tab2:
            medicos = next((ator for ator in faixa_atual['atores'] if ator['ator'] == "MÉDICOS"), None)
            if not medicos:
                medicos = next((ator for ator in faixa_atual['atores'] if "MÉDICOS" in ator['ator']), None)
            
            if medicos:
                for conduta in medicos['condutas']:
                    st.subheader(conduta['conduta'])
                    for procedimento in conduta['procedimentos']:
                        is_selected = (
                            'procedimento_selecionado' in st.session_state and
                            st.session_state.procedimento_selecionado['procedimento']['procedimento'] == procedimento['procedimento'] and
                            st.session_state.procedimento_selecionado['tipo'] == 'MÉDICOS'
                        )
                        
                        if st.button(
                            f"• {procedimento['procedimento']}",
                            key=f"medicos_{hash(procedimento['procedimento'])}",
                            use_container_width=True,
                            type="secondary" if not is_selected else "primary"
                        ):
                            st.session_state.procedimento_selecionado = {
                                'tipo': 'MÉDICOS',
                                'procedimento': procedimento,
                                'faixa_info': faixa_info,
                                'faixa_nome': faixa_nome,
                                'faixa_id': faixa_id
                            }
                            st.rerun()

# Área principal
if 'procedimento_selecionado' in st.session_state:
    proc = st.session_state.procedimento_selecionado
    faixa_info = proc['faixa_info']

    # Objetivo
    st.markdown(f'<div class="objective-box">🎯 Objetivo: {faixa_info["objetivo"]}</div>', unsafe_allow_html=True)

    # Contexto Clínico
    st.markdown(f'<div class="context-box"><strong>⚕️ Contexto Clínico: </strong> {faixa_info["contexto"]}</div>', unsafe_allow_html=True)

    # Procedimento
    st.markdown(f'<div class="procedure-header">🏥 Procedimento: {proc["procedimento"]["procedimento"]}</div>', unsafe_allow_html=True)

    # Motivos (se disponíveis)
    if proc['procedimento']['motivos']:
        motivos = proc['procedimento']['motivos']

        col1, col2 = st.columns(2)

        with col1:
            if motivos.get('fundamento'):
                st.markdown('<div class="section-header">🫀 Fundamento Fisiológico</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-content fundament-section">{motivos["fundamento"]}</div>', unsafe_allow_html=True)

            if motivos.get('evidencias'):
                st.markdown('<div class="section-header">🩺 Evidências Clínicas</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-content evidence-section">{motivos["evidencias"]}</div>', unsafe_allow_html=True)

        with col2:
            if motivos.get('riscos'):
                st.markdown('<div class="section-header">⚠️ Riscos da Omissão</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-content risk-section">{motivos["riscos"]}</div>', unsafe_allow_html=True)
            
            if motivos.get('impacto'):
                st.markdown('<div class="section-header">🤒 Impacto no Paciente</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="section-content impact-section">{motivos["impacto"]}</div>', unsafe_allow_html=True)
        
        # Botão Limpar Explicação
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button("🧹 Limpar Explicação", type="primary", use_container_width=True):
                del st.session_state.procedimento_selecionado
                st.rerun()
    
    # Se houver ações, mostrar como subseções
    if proc['procedimento']['acoes']:
        st.markdown('<div class="section-header">Ações Específicas</div>', unsafe_allow_html=True)
        
        for acao in proc['procedimento']['acoes']:
            with st.expander(f"🔹 {acao['acao']}"):
                if acao['motivos']:
                    col5, col6 = st.columns(2)
                    
                    with col5:
                        if acao['motivos'].get('fundamento'):
                            st.markdown('<div class="section-header">Fundamento</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="section-content fundament-section">{acao["motivos"]["fundamento"]}</div>', unsafe_allow_html=True)
                        
                        if acao['motivos'].get('riscos'):
                            st.markdown('<div class="section-header">Riscos</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="section-content risk-section">{acao["motivos"]["riscos"]}</div>', unsafe_allow_html=True)
                    
                    with col6:
                        if acao['motivos'].get('evidencias'):
                            st.markdown('<div class="section-header">Evidências</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="section-content evidence-section">{acao["motivos"]["evidencias"]}</div>', unsafe_allow_html=True)
                        
                        if acao['motivos'].get('impacto'):
                            st.markdown('<div class="section-header">Impacto</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="section-content impact-section">{acao["motivos"]["impacto"]}</div>', unsafe_allow_html=True)

else:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style='background-color: #d1fae5; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid #10b981;'>
            <h4 style='color: #065f46; margin-bottom: 1rem;'>🟢 Faixa Verde (0-2)</h3>
            <p style='color: #047857;'><strong>Baixo risco</strong><br>Monitoração de rotina<br>Sinais vitais a cada 4-8h</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='background-color: #fef3c7; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid #f59e0b;'>
            <h4 style='color: #92400e; margin-bottom: 1rem;'>🟡 Faixa Amarela (3-4)</h3>
            <p style='color: #b45309;'><strong>Risco moderado</strong><br>Vigilância ativa<br>Monitoração a cada 2h</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='background-color: #fee2e2; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid #ef4444;'>
            <h4 style='color: #991b1b; margin-bottom: 1rem;'>🔴 Faixa Vermelha (≥5)</h3>
            <p style='color: #b91c1c;'><strong>Alto risco</strong><br>Intervenção imediata<br>Monitoração contínua</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style='margin-top: 2rem; padding: 1.5rem; background-color: #eff6ff; border-radius: 0.5rem;'>
        <h3 style='color: #1e40af; margin-bottom: 1rem;'>📋 Instruções de Uso</h3>
        <ol style='color: #374151; line-height: 1.8;'>
            <li><strong>Selecione o Escore MEWS</strong> na barra lateral (0-15)</li>
            <li><strong>Navegue pelos procedimentos</strong> de Enfermagem e Médicos</li>
            <li><strong>Clique em qualquer Procedimento</strong> para ver detalhes completos</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    
    with st.expander("Conteúdo utilizado para treinar o Modelo:"):
        st.write('''
            📋 Normas da ANVISA:\n
                1. RDC nº 50/2002
                2. RDC nº 222/2018
                3. RDC nº 67/2020
                4. RDC nº 36/2013
                5. RDC nº 15/2012
                6. RDC nº 214/2018
                7. RDC nº 158/2021
        ''')

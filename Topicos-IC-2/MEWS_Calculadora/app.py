# CALCULADORA MEWS

import streamlit as st
import os
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Calculadora MEWS",
    page_icon="📟",
    layout="wide"
)

# Título principal
st.title("📟 Calculadora MEWS")

# Definir o caminho base do projeto
PROJECT_ROOT = Path(__file__).parent

# Carrega o arquivo CSS
css_path = PROJECT_ROOT / "styles" / "styles.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
else:
    st.error(f"Arquivo CSS não encontrado em: {css_path}")

# Exibir tabela de pontuação na área principal
st.header("Tabela de Pontuação MEWS")
st.markdown("""
| Parâmetro                               | 3     | 2     | 1         | 0         | 1         | 2     | 3         |
|-----------------------------------------|-------|-------|-----------|-----------|-----------|-------|-----------|
| FC - Frequência Cardíaca (bpm)          | ≤40   | 41-50 | 51-100    | 101-110   | 111-129   | ≥130  |           |
| PAS - Pressão Arterial Sistólica (mmHg) | ≤70   | 71-80 | 81-100    | 101-199   |           | ≥200  |           |
| FR - Frequência Respiratória (rpm)      | ≤8    |       | 9-14      | 15-20     | 21-29     | ≥30   |           |
| TC - Temperatura Corporal (°C)          | ≤35.0 |       | 35.1-36.0 | 36.1-38.0 | 38.1-38.5 | ≥38.6 |           |
| AVPU - Nível de Consciência             |       |       |           |     A     |     V     |   P   |     U     |
""")

# Sidebar para entrada de dados
st.sidebar.header("🔣 Entrada de Parâmetros Clínicos")

# Criar cada linha com label e input lado a lado
fc_col1, fc_col2 = st.sidebar.columns([6, 4])
with fc_col1:
    st.write("Frequência Cardíaca (bpm):")
with fc_col2:
    fc = st.number_input("", min_value=0.0, max_value=150.0, value=80.0, step=0.5, key="fc_input", label_visibility="collapsed")

pas_col1, pas_col2 = st.sidebar.columns([6, 4])
with pas_col1:
    st.write("Pressão Arterial Sistólica (mmHg):")
with pas_col2:
    pas = st.number_input("", min_value=0.0, max_value=220.0, value=120.0, step=0.5, key="pas_input", label_visibility="collapsed")

fr_col1, fr_col2 = st.sidebar.columns([6, 4])
with fr_col1:
    st.write("Frequência Respiratória (rpm):")
with fr_col2:
    fr = st.number_input("", min_value=0.0, max_value=40.0, value=16.0, step=0.1, key="fr_input", label_visibility="collapsed")

tc_col1, tc_col2 = st.sidebar.columns([6, 4])
with tc_col1:
    st.write("Temperatura Corporal (°C):")
with tc_col2:
    tc = st.number_input("", min_value=30.0, max_value=45.0, value=36.5, step=0.1, key="tc_input", label_visibility="collapsed")

avpu_col1, avpu_col2 = st.sidebar.columns([6, 4])
with avpu_col1:
    st.write("Nível de Consciência (AVPU):")
with avpu_col2:
    avpu = st.selectbox("", options=["A", "V", "P", "U"], key="avpu_input", label_visibility="collapsed")

# Adicionar um pouco de espaço
st.sidebar.write("")

# Botão para calcular
calcular = st.sidebar.button("Calcular MEWS", type="primary", use_container_width=True)

# Inicializar variáveis
total_score = 0
faixa = 0
risco = ""
interpretacao = ""

# Cálculo quando o botão for pressionado
if calcular:
    # Cálculo dos escores individuais
    score_fc = 0
    if fc <= 40: score_fc = 3
    elif 41 <= fc <= 50: score_fc = 2
    elif 51 <= fc <= 100: score_fc = 1
    elif 101 <= fc <= 110: score_fc = 0
    elif 111 <= fc <= 129: score_fc = 1
    else: score_fc = 2

    score_pas = 0
    if pas <= 70: score_pas = 3
    elif 71 <= pas <= 80: score_pas = 2
    elif 81 <= pas <= 100: score_pas = 1
    elif 101 <= pas <= 199: score_pas = 0
    else: score_pas = 2

    score_fr = 0
    if fr <= 8: score_fr = 3
    elif 9 <= fr <= 14: score_fr = 1
    elif 15 <= fr <= 20: score_fr = 0
    elif 21 <= fr <= 29: score_fr = 1
    else: score_fr = 2

    score_tc = 0
    if tc <= 35.0: score_tc = 3
    elif 35.1 <= tc <= 36.0: score_tc = 1
    elif 36.1 <= tc <= 38.0: score_tc = 0
    elif 38.1 <= tc <= 38.5: score_tc = 1
    else: score_tc = 2

    if avpu == "A": score_avpu = 0
    if avpu == "V": score_avpu = 1
    if avpu == "P": score_avpu = 2
    if avpu == "U": score_avpu = 3

    # Cálculo do escore total
    total_score = score_fc + score_pas + score_fr + score_tc + score_avpu

    # Determinação da faixa de risco
    if total_score <= 2:
        faixa = 1
        risco = "Normal (Verde)"
        interpretacao = "Baixo Risco - Continuação da monitoração de rotina"
    elif 3 <= total_score <= 4:
        faixa = 2
        risco = "Alerta (Amarelo)"
        interpretacao = "Risco Moderado - Aumentar frequência de observação e informar equipe sênior"
    else:
        faixa = 3
        risco = "Emergência (Vermelho)"
        interpretacao = "Alto Risco - Avaliação médica imediata necessária"

    # Exibição dos resultados
    st.write("#### Resultado da Avaliação MEWS:")
    col1, col2, col3 = st.columns([1.7, 1.7, 3.6])
    with col1:
        # st.info(f"Escore MEWS Total: {total_score}")
        st.markdown(f'<div class="context-box">Escore MEWS Total: <b>{total_score}</b></div>', unsafe_allow_html=True)
    with col2:
        # st.info(f"Faixa de Risco: {faixa} - Classificação: {risco}")
        if faixa == 1:
            st.markdown(f'<div class="classification-box"><b>Faixa de Risco:</b><br>{faixa} - Classificação: {risco}</div>', unsafe_allow_html=True)
        elif faixa == 2:
            st.markdown(f'<div class="classification-box-amarelo"><b>Faixa de Risco:</b><br>{faixa} - Classificação: {risco}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="classification-box-vermelho"><b>Faixa de Risco:</b><br>{faixa} - Classificação: {risco}</div>', unsafe_allow_html=True)
    with col3:    
        #st.info(f"**Interpretação:** {interpretacao}")
        # st.markdown(f'<div class="procedure-header">🎯 Interpretação: {interpretacao}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="objective-box"><b>🎯 Interpretação:</b><br>{interpretacao}</div>', unsafe_allow_html=True)

    st.divider()

    # Tabela de referência de escores com percentuais
    st.write("#### Detalhamento dos Escores")
    
    # Calcular percentuais
    if total_score > 0:
        percent_fc = (score_fc / total_score) * 100
        percent_pas = (score_pas / total_score) * 100
        percent_fr = (score_fr / total_score) * 100
        percent_tc = (score_tc / total_score) * 100
        percent_avpu = (score_avpu / total_score) * 100
    else:
        percent_fc = percent_pas = percent_fr = percent_tc = percent_avpu = 0.0
    
    # Calcular soma dos percentuais
    soma_percentuais = percent_fc + percent_pas + percent_fr + percent_tc + percent_avpu
    
    # Criar dados da tabela
    tabela_dados = {
        "Parâmetro": ["FC - Frequência Cardíaca (bpm)", 
                     "Pressão Arterial Sistólica (mmHg)", 
                     "FR - Frequência Respiratória (rpm)", 
                     "TC - Temperatura Corporal (°C)", 
                     "AVPU - Nível de Consciência",
                     "Totais:"],
        "Escore": [score_fc, score_pas, score_fr, score_tc, score_avpu, f"{total_score}"],
        "(%)": [f"{percent_fc:.2f}%", 
               f"{percent_pas:.2f}%", 
               f"{percent_fr:.2f}%", 
               f"{percent_tc:.2f}%", 
               f"{percent_avpu:.2f}%", 
               f"{soma_percentuais:.2f}%"],
        "Valor Inserido": [fc, pas, fr, tc, avpu, ""],
        "Valor Ideal": ["101-110", "101-199", "15-20", "36.1-38.0", "A", ""]
    }
    
    st.table(tabela_dados)

# Instruções de uso (sempre visível)
with st.expander("ℹ️ Sobre a Escala MEWS"):
    st.markdown("""
    **Interpretação do Escore MEWS Total:**
    - **Score 0-2:** Baixo Risco (Faixa 1/Verde) - Monitoração de rotina
    - **Score 3-4:** Risco Moderado (Faixa 2/Amarelo) - Aumentar observação
    - **Score ≥5:** Alto Risco (Faixa 3/Vermelho) - Requer avaliação imediata

    **Parâmetros Avaliados:**
    1. **FC:** Frequência Cardíaca
    2. **PAS:** Pressão Arterial Sistólica
    3. **FR:** Frequência Respiratória
    4. **TC:** Temperatura Corporal
    5. **AVPU:** Nível de Consciência
        - A: Alerta
        - V: Responde a estímulos verbais
        - P: Responde a estímulos dolorosos
        - U: Inconsciente
    """)

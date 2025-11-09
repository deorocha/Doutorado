import streamlit as st
import PyPDF2
import os
import re
from collections import Counter
from unidecode import unidecode
from lingua import Language, LanguageDetectorBuilder
from wordcloud import WordCloud
import numpy as np
from PIL import Image
import io
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
CSS_PATH = PROJECT_ROOT / "styles" / "styles.css"
IMAGES_PATH = PROJECT_ROOT / "images"
fluxograma_image_path = IMAGES_PATH / "fluxograma.png"
stopwords_path = PROJECT_ROOT / "arquivos" / "files_txt" / "stopwords.txt"
pasta_pdf = PROJECT_ROOT / "arquivos" / "files_pdf"
mascara_path = IMAGES_PATH / "shape.png"

# Carregar CSS externo com codificação correta
def load_css(css_path):
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Arquivo CSS não encontrado na pasta 'styles/'")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")
load_css(CSS_PATH)

st.title("☁️ Gerador de Word Clouds")

def remover_acentos(texto):
    return unidecode(texto)

def processar_pdf(caminho_arquivo):
    """Extrai e processa o texto de um arquivo PDF"""
    try:
        with open(caminho_arquivo, 'rb') as arquivo:
            leitor = PyPDF2.PdfReader(arquivo)
            texto_completo = ""
            
            for pagina in leitor.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto_completo += texto_pagina + " "
            
            return texto_completo
    except Exception as e:
        st.error(f"Erro ao processar {caminho_arquivo}: {e}")
        return ""

def processar_texto(texto):
    """Processa o texto: remove números, símbolos, letras gregas e linhas em branco"""
    # Remove números
    texto_sem_numeros = re.sub(r'\d+', '', texto)
    
    # Remove símbolos e caracteres especiais, mantendo apenas letras e espaços
    texto_limpo = re.sub(r'[^\w\s]', ' ', texto_sem_numeros)
    
    # Remove letras gregas (caracteres Unicode do bloco grego)
    texto_sem_grego = re.sub(r'[\u0370-\u03FF\u1F00-\u1FFF]', '', texto_limpo)
    
    # Remove espaços múltiplos e quebras de linha
    texto_final = re.sub(r'\s+', ' ', texto_sem_grego).strip()
    
    return texto_final

def inicializar_detector_idioma():
    """Inicializa o detector de idioma para português e inglês"""
    languages = [Language.PORTUGUESE, Language.ENGLISH]
    detector = LanguageDetectorBuilder.from_languages(*languages).build()
    return detector

def is_palavra_portugues(palavra, detector):
    """
    Verifica se a palavra é em português usando Lingua-py
    """
    # Palavras muito curtas não são bem detectadas pelo Lingua-py
    if len(palavra) < 3:
        return False
    
    try:
        # O detector retorna o idioma mais provável
        detected_language = detector.detect_language_of(palavra)
        
        # Considera como português apenas se for detectado como PORTUGUESE
        # e não for ENGLISH
        if detected_language == Language.PORTUGUESE:
            return True
        else:
            return False
            
    except Exception:
        # Em caso de erro na detecção, assume como não português
        return False

def is_sigla(palavra):
    """
    Verifica se a palavra é uma sigla
    Uma palavra é considerada sigla se:
    - Tem pelo menos 2 caracteres
    - Todos os caracteres são maiúsculos
    - Ou tem mistura de maiúsculas e números
    """
    if len(palavra) < 2:
        return False
    
    # Verifica se todos os caracteres são maiúsculos
    if palavra.isupper():
        return True
    
    # Verifica se tem mistura de maiúsculas e números (ex: ISO9001)
    if any(c.isupper() for c in palavra) and not any(c.islower() for c in palavra):
        return True
    
    return False

def carregar_stopwords_padrao():
    """Carrega as stopwords padrão do arquivo de stopwords"""
    stopwords_padrao = set()
    
    try:
        if stopwords_path.exists():
            with open(stopwords_path, 'r', encoding='utf-8') as arquivo:
                for linha in arquivo:
                    palavra = linha.strip().lower()
                    if palavra:
                        palavra_sem_acento = remover_acentos(palavra)
                        stopwords_padrao.add(palavra_sem_acento)
            # st.write(f"✅ {len(stopwords_padrao)} stopwords carregadas do arquivo padrão")
        else:
            st.warning(f"Arquivo {stopwords_path} não encontrado. Será criado um conjunto vazio de stopwords.")
    except Exception as e:
        st.error(f"Erro ao carregar stopwords: {e}")
    
    return stopwords_padrao

def gerar_wordcloud(palavras_ocorrencias, quantidade_palavras, fonte_min, fonte_max, mascara_path):
    """Gera uma word cloud baseada nas palavras e ocorrências"""
    try:
        # Filtra as palavras pela quantidade selecionada
        palavras_selecionadas = dict(palavras_ocorrencias[:quantidade_palavras])
        
        if not palavras_selecionadas:
            st.error("Nenhuma palavra disponível para gerar a nuvem de palavras.")
            return None
        
        # Carrega a máscara se existir
        mascara = None
        if mascara_path.exists():
            try:
                mascara = np.array(Image.open(mascara_path))
            except Exception as e:
                st.warning(f"Não foi possível carregar a máscara: {e}")
        else:
            st.warning(f"Máscara não encontrada em {mascara_path}. Gerando word cloud sem máscara.")
        
        # Configura a word cloud
        wc = WordCloud(
            width=1200,
            height=800,
            background_color='white',
            min_font_size=fonte_min,
            max_font_size=fonte_max,
            colormap='viridis',
            mask=mascara,
            relative_scaling=0.5,
            random_state=42,
            prefer_horizontal=0.9
        )
        
        # Gera a word cloud
        wordcloud = wc.generate_from_frequencies(palavras_selecionadas)
        
        # Converte a word cloud para imagem PIL
        image = wordcloud.to_image()
        
        return image
        
    except Exception as e:
        st.error(f"Erro ao gerar word cloud: {e}")
        return None

def main():
    # Inicializa o detector de idioma
    with st.spinner("Inicializando detector de idiomas..."):
        detector_idioma = inicializar_detector_idioma()
    st.write("✅ Detector de idiomas inicializado")
    
    # Verifica se a patopwords carregadas do arquivo padrãosta existe
    if not pasta_pdf.exists():
        st.error(f"A pasta '{pasta_pdf}' não foi encontrada!")
        return
    
    # Lista arquivos PDF na pasta
    arquivos_pdf = [f for f in os.listdir(pasta_pdf) if f.lower().endswith('.pdf')]
    
    if not arquivos_pdf:
        st.warning(f"Nenhum arquivo PDF encontrado na pasta '{pasta_pdf}'")
        return
    
    st.write(f"📁 **Arquivos PDF encontrados: {len(arquivos_pdf)}**")
    
    # Carrega stopwords padrão
    stopwords_padrao = carregar_stopwords_padrao()
    
    # Seção para stopwords personalizadas
    st.subheader("🛑 Stopwords Personalizadas")
    st.write("Informe palavras adicionais que não devem ser consideradas na análise (separadas por vírgula):")
    
    # Preenche o textarea com as stopwords padrão (apenas para visualização)
    if stopwords_padrao:
        stopwords_padrao_texto = ", ".join(sorted(list(stopwords_padrao))[:50])  # Mostra até 50 palavras
        if len(stopwords_padrao) > 50:
            stopwords_padrao_texto += f"... (e mais {len(stopwords_padrao) - 50} palavras)"
        
        st.write(f"**Stopwords padrão carregadas:** {stopwords_padrao_texto}")
    
    stopwords_input = st.text_area(
        "Stopwords adicionais:",
        value="",
        height=100,
        placeholder="Exemplo: empresa, sistema, projeto, trabalho, desenvolvimento, processo..."
    )
    
    # Combina stopwords padrão com as personalizadas
    stopwords_combinadas = stopwords_padrao.copy()
    
    if stopwords_input:
        stopwords_list = [word.strip().lower() for word in stopwords_input.split(',')]
        stopwords_personalizadas = {remover_acentos(word) for word in stopwords_list if word}
        stopwords_combinadas.update(stopwords_personalizadas)
        
        st.write(f"**Total de stopwords ativas:** {len(stopwords_combinadas)} palavras")
    
    # Processa todos os PDFs
    if st.button("🔍 Processar PDFs"):
        with st.spinner("Processando arquivos PDF..."):
            todas_palavras = []
            palavras_filtradas_info = []
            
            # Cria a barra de progresso
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_arquivos = len(arquivos_pdf)
            
            for indice, arquivo_pdf in enumerate(arquivos_pdf):
                caminho_completo = pasta_pdf / arquivo_pdf
                
                # Atualiza a barra de progresso (0-100%)
                percentual = int((indice / total_arquivos) * 100)
                progress_bar.progress(percentual)
                status_text.text(f"Progresso: {percentual}% - Processando: ({indice+1}/{total_arquivos})")
                
                texto_pdf = processar_pdf(caminho_completo)
                texto_processado = processar_texto(texto_pdf)
                
                # Divide em palavras e adiciona ao array
                palavras = texto_processado.lower().split()
                palavras_sem_acentos = [remover_acentos(palavra) for palavra in palavras]
                
                # Filtra palavras
                palavras_validas = []
                for palavra in palavras_sem_acentos:
                    palavra = palavra.strip()
                    
                    # Verifica comprimento mínimo
                    if len(palavra) < 5:
                        palavras_filtradas_info.append(f"'{palavra}' - tamanho < 5")
                        continue
                    
                    # Verifica se é sigla
                    if is_sigla(palavra):
                        palavras_filtradas_info.append(f"'{palavra}' - sigla")
                        continue
                    
                    # Verifica se é palavra em português usando Lingua-py
                    if not is_palavra_portugues(palavra, detector_idioma):
                        palavras_filtradas_info.append(f"'{palavra}' - não é português")
                        continue
                    
                    # Verifica se está nas stopwords combinadas
                    if palavra in stopwords_combinadas:
                        palavras_filtradas_info.append(f"'{palavra}' - stopword")
                        continue
                    
                    palavras_validas.append(palavra)
                
                todas_palavras.extend(palavras_validas)
            
            # Completa a barra de progresso (100%)
            progress_bar.progress(100)
            status_text.text("Processamento concluído! Gerando resultados...")
            
            # Ordena em ordem alfabética
            todas_palavras.sort()
            
            # Cria array com palavras e ocorrências
            contador_palavras = Counter(todas_palavras)
            
            # Filtra palavras com menos de 2 ocorrências
            palavras_ocorrencias = [(palavra, quantidade) for palavra, quantidade in contador_palavras.items() 
                                  if quantidade >= 2]
            
            # Ordena por ocorrências (decrescente)
            palavras_ocorrencias.sort(key=lambda x: x[1], reverse=True)
            
            # Limpa o status text
            status_text.empty()
            
            # Armazena os resultados na sessão para uso posterior
            st.session_state.palavras_ocorrencias = palavras_ocorrencias
            
            # Mostra resultados
            st.success("✅ Processamento concluído!")
            
            # Estatísticas de filtragem
            st.subheader("📊 Estatísticas de Filtragem")
            col1, col2, col3 = st.columns(3)
            
            total_palavras_processadas = len(palavras_filtradas_info) + len(todas_palavras)
            palavras_unicas_iniciais = len(contador_palavras)
            palavras_apos_filtro = len(palavras_ocorrencias)
            
            with col1:
                st.metric("Palavras processadas", total_palavras_processadas)
                st.metric("Palavras filtradas", len(palavras_filtradas_info))
            
            with col2:
                st.metric("Palavras válidas", len(todas_palavras))
                st.metric("Palavras únicas iniciais", palavras_unicas_iniciais)
            
            with col3:
                st.metric("Arquivos processados", len(arquivos_pdf))
                st.metric("Palavras após filtro (≥2 ocorrências)", palavras_apos_filtro)
            
            # Mostra exemplos de palavras filtradas
            with st.expander("🔍 Ver exemplos de palavras filtradas"):
                if palavras_filtradas_info:
                    # Agrupa por motivo de filtragem
                    filtros = {}
                    for info in palavras_filtradas_info[:200]:  # Mostra apenas os 200 primeiros
                        partes = info.split(' - ')
                        if len(partes) == 2:
                            motivo = partes[1]
                            palavra = partes[0].replace("'", "")
                            if motivo not in filtros:
                                filtros[motivo] = set()
                            filtros[motivo].add(palavra)
                    
                    for motivo, palavras_set in filtros.items():
                        # Convertendo o set para lista para poder fazer slice
                        palavras_lista = list(palavras_set)
                        st.write(f"**{motivo}:** {', '.join(palavras_lista[:10])}")
                        if len(palavras_lista) > 10:
                            st.write(f"... e mais {len(palavras_lista) - 10} palavras")
                else:
                    st.write("Nenhuma palavra foi filtrada.")
            
            # Mostra palavras removidas por terem menos de 2 ocorrências
            palavras_removidas_baixa_frequencia = [palavra for palavra, quantidade in contador_palavras.items() 
                                                 if quantidade < 2]
            
            if palavras_removidas_baixa_frequencia:
                with st.expander("🔍 Ver palavras removidas (menos de 2 ocorrências)"):
                    st.write(f"**Total de palavras removidas por baixa frequência:** {len(palavras_removidas_baixa_frequencia)}")
                    # Agrupa em colunas para melhor visualização
                    col1, col2, col3 = st.columns(3)
                    palavras_por_coluna = len(palavras_removidas_baixa_frequencia) // 3 + 1
                    
                    with col1:
                        for palavra in palavras_removidas_baixa_frequencia[:palavras_por_coluna]:
                            st.write(f"- {palavra}")
                    
                    with col2:
                        for palavra in palavras_removidas_baixa_frequencia[palavras_por_coluna:palavras_por_coluna*2]:
                            st.write(f"- {palavra}")
                    
                    with col3:
                        for palavra in palavras_removidas_baixa_frequencia[palavras_por_coluna*2:]:
                            st.write(f"- {palavra}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📈 Top 15 Palavras Mais Frequentes")
                if palavras_ocorrencias:
                    for i, (palavra, quantidade) in enumerate(palavras_ocorrencias[:15], 1):
                        st.write(f"{i}. **{palavra}** - {quantidade} ocorrências")
                else:
                    st.write("Nenhuma palavra atende aos critérios de filtragem")
            
            with col2:
                st.subheader("📉 Palavras Menos Frequentes")
                if palavras_ocorrencias:
                    palavras_menos_frequentes = palavras_ocorrencias[-15:] if len(palavras_ocorrencias) >= 15 else palavras_ocorrencias
                    for i, (palavra, quantidade) in enumerate(palavras_menos_frequentes, 1):
                        st.write(f"{i}. **{palavra}** - {quantidade} ocorrências")
                else:
                    st.write("Nenhuma palavra atende aos critérios de filtragem")
            
            # Mostra tabela completa
            st.subheader("📋 Lista Completa de Palavras e Ocorrências")
            
            if palavras_ocorrencias:
                # Cria DataFrame para melhor visualização
                import pandas as pd
                df = pd.DataFrame(palavras_ocorrencias, columns=['Palavra', 'Ocorrências'])
                
                st.dataframe(df, use_container_width=True)
                
                # Opção de download - botões na mesma linha
                st.subheader("💾 Download dos Resultados")
                col_download1, col_download2 = st.columns(2)
                
                with col_download1:
                    # Salva como CSV
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Baixar como CSV",
                        data=csv,
                        file_name="analise_palavras_portugues.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col_download2:
                    # Salva como TXT
                    texto_resultado = "Palavra\tOcorrências\n"
                    for palavra, quantidade in palavras_ocorrencias:
                        texto_resultado += f"{palavra}\t{quantidade}\n"
                    
                    st.download_button(
                        label="📥 Baixar como TXT",
                        data=texto_resultado,
                        file_name="analise_palavras_portugues.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
    
    # Seção para Word Cloud - MOVIDA PARA FORA DO BLOCO "Processar PDFs"
    if 'palavras_ocorrencias' in st.session_state:
        st.subheader("☁️ Gerar Nuvem de Palavras")
        
        # Verificação se há dados disponíveis
        if not st.session_state.palavras_ocorrencias:
            st.error("❌ Nenhuma palavra disponível para gerar a nuvem. Processe os PDFs primeiro.")
        else:
            st.info(f"✅ {len(st.session_state.palavras_ocorrencias)} palavras disponíveis para a nuvem")
            
            with st.container():
                st.write("Configure os parâmetros para gerar a nuvem de palavras:")
                
                col_config1, col_config2, col_config3 = st.columns(3)
                
                with col_config1:
                    quantidade_palavras = st.slider(
                        "Quantidade de palavras:",
                        min_value=10,
                        max_value=min(1000, len(st.session_state.palavras_ocorrencias)),
                        value=min(100, len(st.session_state.palavras_ocorrencias)),
                        step=10
                    )
                
                with col_config2:
                    fonte_min = st.slider(
                        "Menor tamanho da Fonte:",
                        min_value=12,
                        max_value=30,
                        value=15,
                        step=1
                    )
                
                with col_config3:
                    fonte_max = st.slider(
                        "Maior Tamanho da Fonte:",
                        min_value=50,
                        max_value=200,
                        value=120,
                        step=10
                    )
            
            # Botão para gerar Word Cloud
            if st.button("✨ Gerar Nuvem de Palavras", type="primary"):
                with st.spinner("Gerando nuvem de palavras..."):
                    wordcloud_image = gerar_wordcloud(
                        st.session_state.palavras_ocorrencias,
                        quantidade_palavras, 
                        fonte_min, 
                        fonte_max, 
                        mascara_path
                    )
                    
                    if wordcloud_image:
                        # Exibe a word cloud
                        st.image(wordcloud_image, caption=f'Nuvem de Palavras - Top {quantidade_palavras} Palavras', 
                                use_container_width=True)
                        st.success("✅ Nuvem de palavras gerada com sucesso!")
                        
                        # Botão para salvar a Word Cloud
                        st.subheader("💾 Salvar Word Cloud")
                        
                        # Converte a imagem para bytes
                        img_buffer = io.BytesIO()
                        wordcloud_image.save(img_buffer, format='PNG')
                        img_buffer.seek(0)
                        
                        # Botão único para salvar como PNG
                        st.download_button(
                            label="💾 Salvar Word Cloud (.png)",
                            data=img_buffer,
                            file_name="nuvem_palavras.png",
                            mime="image/png",
                            use_container_width=True
                        )
    else:
        st.info("ℹ️ Processe os PDFs primeiro para habilitar a geração da nuvem de palavras")

if __name__ == "__main__":
    main()

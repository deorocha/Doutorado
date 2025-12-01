# app.py - VERSÃO COM DOC2VEC PARA STREAMLIT CLOUD

import streamlit as st
import os
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')
from model_trainer import Doc2VecModelManager
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
FILES_PDF = PROJECT_ROOT / "files_pdf"
FILES_TARGET = PROJECT_ROOT / "files_target"

# Configurar página
st.set_page_config(
    page_title="Análise de Similaridade Doc2Vec",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
[data-testid="stMetricValue"] {
    font-size: 20px;
}
.stDataFrame {
    font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

# Configuração
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Estados da sessão
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'df_results' not in st.session_state:
    st.session_state.df_results = None
if 'stats_dict' not in st.session_state:
    st.session_state.stats_dict = None
if 'base_stats' not in st.session_state:
    st.session_state.base_stats = None
if 'base_doc' not in st.session_state:
    st.session_state.base_doc = None
if 'model_params' not in st.session_state:
    st.session_state.model_params = None

def list_pdf_files(folder_path):
    """Lista PDFs em uma pasta"""
    import glob
    if not os.path.exists(folder_path):
        os.makedirs(folder_path, exist_ok=True)
        return []
    
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    return sorted(pdf_files)

def analyze_documents():
    """Função principal de análise"""
    base_pdf_files = list_pdf_files(FILES_TARGET)
    comparison_pdf_files = list_pdf_files(FILES_PDF)
    
    if not base_pdf_files:
        st.error("❌ Adicione um documento base em './files_target/'")
        return None
    
    if not comparison_pdf_files:
        st.error("❌ Adicione documentos para comparação em './files_pdf/'")
        return None
    
    # Encontrar documento base
    base_pdf_path = next((f for f in base_pdf_files 
                         if os.path.basename(f) == st.session_state.base_doc), None)
    
    if not base_pdf_path:
        st.error("❌ Documento base não encontrado")
        return None
    
    # Inicializar modelo
    model_manager = Doc2VecModelManager()
    
    # Treinar modelo com documento base
    with st.spinner("🏋️ Treinando modelo Doc2Vec..."):
        model = model_manager.train_model_for_document(
            base_pdf_path,
            vector_size=st.session_state.model_params['vector_size'],
            window=st.session_state.model_params['window'],
            min_count=st.session_state.model_params['min_count'],
            epochs=st.session_state.model_params['epochs']
        )
    
    if not model:
        st.error("❌ Falha ao treinar modelo")
        return None
    
    # Obter embedding do documento base
    base_stats = model_manager.calculate_document_stats(base_pdf_path)
    if not base_stats:
        st.error("❌ Falha ao processar documento base")
        return None
    
    base_embedding = model_manager.infer_document_embedding(model, base_stats['text'])
    if base_embedding is None:
        st.error("❌ Falha ao gerar embedding do documento base")
        return None
    
    # Processar outros documentos
    results = []
    progress_bar = st.progress(0)
    
    for i, pdf_file in enumerate(comparison_pdf_files):
        progress = (i + 1) / len(comparison_pdf_files)
        progress_bar.progress(progress)
        
        file_name = os.path.basename(pdf_file)
        doc_stats = model_manager.calculate_document_stats(pdf_file)
        
        if not doc_stats:
            continue
        
        doc_embedding = model_manager.infer_document_embedding(model, doc_stats['text'])
        if doc_embedding is None:
            continue
        
        # Calcular similaridade
        similarity = cosine_similarity([base_embedding], [doc_embedding])[0][0]
        
        results.append({
            'arquivo': file_name,
            'similaridade': similarity,
            'paginas': doc_stats['num_pages'],
            'tamanho_texto': doc_stats['text_length'],
            'sentencas': doc_stats['num_sentences']
        })
    
    progress_bar.empty()
    
    if not results:
        st.error("❌ Nenhum resultado obtido")
        return None
    
    # Criar DataFrame
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('similaridade', ascending=False)
    
    # Calcular estatísticas
    stats_dict = {
        'Média': df_results['similaridade'].mean(),
        'Mediana': df_results['similaridade'].median(),
        'Desvio Padrão': df_results['similaridade'].std(),
        'Mínimo': df_results['similaridade'].min(),
        'Máximo': df_results['similaridade'].max(),
        'Amplitude': df_results['similaridade'].max() - df_results['similaridade'].min(),
    }
    
    return df_results, stats_dict, base_stats

def create_visualizations(df_results):
    """Cria visualizações dos resultados"""
    figs = []
    
    # 1. Top 10 documentos similares
    fig1, ax1 = plt.subplots(figsize=(12, 8))
    top_10 = df_results.head(10).copy()
    y_pos = np.arange(len(top_10))
    
    colors = plt.cm.viridis(top_10['similaridade'])
    bars = ax1.barh(y_pos, top_10['similaridade'], color=colors)
    
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(top_10['arquivo'].apply(
        lambda x: x[:20] + '...' if len(x) > 20 else x
    ), fontsize=10)
    ax1.invert_yaxis()
    ax1.set_xlabel('Similaridade (Doc2Vec)', fontsize=12)
    ax1.set_xlim(0, 1)
    ax1.grid(True, axis='x', alpha=0.3)
    
    for i, (bar, value) in enumerate(zip(bars, top_10['similaridade'])):
        ax1.text(value + 0.01, bar.get_y() + bar.get_height()/2, 
                f'{value:.3f}', va='center', fontsize=10, fontweight='bold')
    
    figs.append(fig1)
    
    # 2. Distribuição das similaridades (COM LABELS NAS BARRAS)
    fig2, ax2 = plt.subplots(figsize=(12, 8))
    hist_values, bins, patches = ax2.hist(df_results['similaridade'], bins=15, 
                                          edgecolor='black', alpha=0.7, color='skyblue')
    
    # Adicionar labels com os valores sobre as barras
    for i, (patch, value) in enumerate(zip(patches, hist_values)):
        if value > 0:  # Só adicionar label se houver valor
            ax2.text(patch.get_x() + patch.get_width()/2, 
                    value + 0.1, 
                    str(int(value)), 
                    ha='center', va='bottom', 
                    fontsize=10, fontweight='bold')
    
    ax2.axvline(df_results['similaridade'].mean(), color='red', 
                linestyle='--', linewidth=2, label=f'Média: {df_results["similaridade"].mean():.3f}')
    ax2.axvline(df_results['similaridade'].median(), color='green', 
                linestyle='--', linewidth=2, label=f'Mediana: {df_results["similaridade"].median():.3f}')
    
    ax2.set_xlabel('Similaridade', fontsize=12)
    ax2.set_ylabel('Frequência', fontsize=12)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    figs.append(fig2)
    
    # 3. Similaridade vs Tamanho do Texto (COM LABELS)
    fig3, ax3 = plt.subplots(figsize=(12, 8))
    scatter = ax3.scatter(df_results['tamanho_texto'], df_results['similaridade'], 
                         c=df_results['similaridade'], cmap='viridis', 
                         s=80, alpha=0.7, edgecolors='black', linewidth=0.5)
    
    # Adicionar labels nos pontos (apenas para os top 10 para não poluir)
    top_10_for_labels = df_results.head(10).copy()
    for _, row in top_10_for_labels.iterrows():
        ax3.annotate(
            row['arquivo'][:15] + ('...' if len(row['arquivo']) > 15 else ''),  # Nome truncado
            (row['tamanho_texto'], row['similaridade']),
            xytext=(5, 5),
            textcoords='offset points',
            fontsize=9,
            alpha=0.8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='gray', linewidth=0.5)
        )
    
    ax3.set_xlabel('Tamanho do Texto (caracteres)', fontsize=12)
    ax3.set_ylabel('Similaridade', fontsize=12)
    
    cbar = plt.colorbar(scatter, ax=ax3)
    cbar.set_label('Similaridade', fontsize=10)
    ax3.grid(True, alpha=0.3)
    
    figs.append(fig3)
    
    # 4. Mapa de Calor - Correlações
    fig4, ax4 = plt.subplots(figsize=(12, 8))
    correlation_cols = ['similaridade', 'paginas', 'tamanho_texto', 'sentencas']
    correlation_df = df_results[correlation_cols]
    
    # Calcular matriz de correlação
    corr_matrix = correlation_df.corr()
    
    # Criar heatmap
    sns.heatmap(corr_matrix, annot=True, fmt='.3f', cmap='coolwarm', 
                center=0, square=True, linewidths=1, 
                cbar_kws={'shrink': 0.8}, ax=ax4)
    
    plt.tight_layout()
    figs.append(fig4)
    
    # 5. Gráfico Radar - Top 5 documentos
    fig5 = create_radar_chart(df_results)
    figs.append(fig5)
    
    # 6. Gráfico de Barras - Similaridade com o Documento Base
    fig6, ax6 = plt.subplots(figsize=(12, 8))
    
    # Selecionar os primeiros 15 documentos para melhor visualização
    display_df = df_results.head(15).copy()
    
    bars = ax6.bar(range(len(display_df)), display_df['similaridade'], 
                  color=plt.cm.plasma(display_df['similaridade']))
    
    ax6.set_xlabel('Documentos', fontsize=12)
    ax6.set_ylabel('Similaridade', fontsize=12)
    ax6.set_xticks(range(len(display_df)))
    ax6.set_xticklabels(display_df['arquivo'].apply(
        lambda x: x[:15] + '...' if len(x) > 15 else x
    ), rotation=45, ha='right', fontsize=10)
    ax6.set_ylim(0, 1)
    ax6.grid(True, axis='y', alpha=0.3)
    
    # Adicionar valores nas barras
    for bar, value in zip(bars, display_df['similaridade']):
        height = bar.get_height()
        ax6.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                f'{value:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    figs.append(fig6)
    
    return figs

def create_radar_chart(df_results, top_n=5):
    """Cria gráfico radar para os top N documentos"""
    
    # Selecionar top N documentos
    top_docs = df_results.head(top_n).copy()
    
    # Normalizar os dados para o radar chart (0-1)
    from sklearn.preprocessing import MinMaxScaler
    
    # Colunas para o radar chart
    radar_cols = ['similaridade', 'paginas', 'tamanho_texto', 'sentencas']
    radar_data = top_docs[radar_cols].copy()
    
    # Normalizar cada coluna individualmente (exceto similaridade que já está em 0-1)
    scaler = MinMaxScaler()
    
    for col in radar_cols[1:]:  # Pular similaridade
        radar_data[col] = scaler.fit_transform(radar_data[[col]]).flatten()
    
    # Ângulos para os eixos
    angles = np.linspace(0, 2 * np.pi, len(radar_cols), endpoint=False).tolist()
    angles += angles[:1]  # Fechar o círculo
    
    # Criar figura
    fig, ax = plt.subplots(figsize=(12, 8), subplot_kw=dict(projection='polar'))
    
    # Cores diferentes para cada documento
    colors = plt.cm.tab10(np.linspace(0, 1, len(top_docs)))
    
    # Plotar cada documento
    for idx, (_, row) in enumerate(top_docs.iterrows()):
        values = radar_data.iloc[idx].tolist()
        values += values[:1]  # Fechar o círculo
        
        ax.plot(angles, values, 'o-', linewidth=2, color=colors[idx], 
                label=row['arquivo'][:20] + ('...' if len(row['arquivo']) > 20 else ''), 
                markersize=8)
        ax.fill(angles, values, color=colors[idx], alpha=0.25)
    
    # Configurar eixos
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(['Similaridade', 'Páginas\n(norm.)', 'Tamanho\n(norm.)', 'Sentenças\n(norm.)'], 
                      fontsize=11, fontweight='bold')
    
    # Configurar grade
    ax.yaxis.grid(True, alpha=0.5)
    ax.xaxis.grid(True, alpha=0.5)
    
    # Configurar limites
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=9)
    
    # Legenda
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=10)
    
    plt.tight_layout()
    return fig

def main():
    st.header("📊 Análise de Similaridade com Doc2Vec")
    st.markdown("""
    Analise a similaridade semântica entre documentos PDF usando o modelo Doc2Vec.
    """)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Documento base
        base_files = list_pdf_files(FILES_TARGET)
        if base_files:
            base_options = [os.path.basename(f) for f in base_files]
            st.session_state.base_doc = st.selectbox(
                "📄 Documento Base", 
                base_options,
                key="base_doc_select"
            )
        else:
            st.warning("Adicione PDFs em './files_target/'")
            st.session_state.base_doc = None
        
        # Parâmetros do modelo
        st.subheader("🤖 Parâmetros do Doc2Vec")
        
        col1, col2 = st.columns(2)
        with col1:
            vector_size = st.slider("Tamanho do Vetor", 50, 300, 100)
            window = st.slider("Janela", 2, 15, 5)
        
        with col2:
            min_count = st.slider("Min Count", 1, 10, 2)
            epochs = st.slider("Épocas", 10, 100, 30)
        
        st.session_state.model_params = {
            'vector_size': vector_size,
            'window': window,
            'min_count': min_count,
            'epochs': epochs
        }
        
        # Botão de análise
        if st.button("🔍 Executar Análise", type="primary", use_container_width=True):
            if not st.session_state.base_doc:
                st.error("Selecione um documento base")
            else:
                with st.spinner("Processando..."):
                    result = analyze_documents()
                    if result:
                        df_results, stats_dict, base_stats = result
                        st.session_state.analysis_complete = True
                        st.session_state.df_results = df_results
                        st.session_state.stats_dict = stats_dict
                        st.session_state.base_stats = base_stats
                        st.success("✅ Análise concluída!")
                        st.rerun()
    
    # Resultados
    if st.session_state.analysis_complete:
        df_results = st.session_state.df_results
        stats_dict = st.session_state.stats_dict
        base_stats = st.session_state.base_stats
        
        # Informações do documento base
        st.write("#### 📄 Documento Base")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tamanho", f"{base_stats['text_length']:,}")
        with col2:
            st.metric("Páginas", base_stats['num_pages'])
        with col3:
            st.metric("Sentenças", base_stats['num_sentences'])
        
        # Métricas
        st.write("#### 📊 Métricas de Similaridade")
        cols = st.columns(4)
        metrics = [
            ("Média", f"{stats_dict['Média']:.4f}"),
            ("Mediana", f"{stats_dict['Mediana']:.4f}"),
            ("Máxima", f"{stats_dict['Máximo']:.4f}"),
            ("Mínima", f"{stats_dict['Mínimo']:.4f}"),
        ]
        
        for col, (label, value) in zip(cols, metrics):
            with col:
                st.metric(label, value)
        
        # Tabela
        st.write("#### 📋 Resultados")
        st.dataframe(
            df_results.style.format({
                'similaridade': '{:.4f}',
                'tamanho_texto': '{:,}'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Visualizações - UMA ÚNICA COLUNA COM 80% DE LARGURA
        st.write("#### 📈 Visualizações")
        
        # Criar container centralizado com 80% de largura
        with st.container():
            # Criar uma coluna com largura personalizada
            col1, col2, col3 = st.columns([1, 8, 1])
            
            with col2:
                # Gerar todos os gráficos
                figs = create_visualizations(df_results)
                
                st.write("##### 1. Top 10 Documentos Mais Similares")
                st.pyplot(figs[0])
                st.markdown("---")
                
                st.write("##### 2. Distribuição das Similaridades")
                st.pyplot(figs[1])
                st.markdown("---")
                
                st.write("##### 3. Similaridade com Documento Base")
                st.pyplot(figs[5])
                st.markdown("---")
                
                st.write("##### 4. Similaridade vs Tamanho do Texto")
                st.pyplot(figs[2])
                st.markdown("---")
                
                st.write("##### 5. Mapa de Calor - Correlações")
                st.pyplot(figs[3])
                st.markdown("---")
                
                st.write("##### 6. Comparação Radar - Top 5 Documentos")
                st.pyplot(figs[4])
        
        # Exportar
        st.write("### 💾 Exportar Resultados")
        col1, col2 = st.columns(2)
        
        with col1:
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 CSV",
                data=csv,
                file_name=f"doc2vec_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        
        with col2:
            report = f"""
            RELATÓRIO DOC2VEC
            Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            
            Documento base: {st.session_state.base_doc}
            Documentos analisados: {len(df_results)}
            
            Estatísticas:
            Média: {stats_dict['Média']:.4f}
            Mediana: {stats_dict['Mediana']:.4f}
            Desvio: {stats_dict['Desvio Padrão']:.4f}
            Mínimo: {stats_dict['Mínimo']:.4f}
            Máximo: {stats_dict['Máximo']:.4f}
            
            Top 5:
            {chr(10).join([f'{i+1}. {row["arquivo"]}: {row["similaridade"]:.4f}' 
                          for i, row in df_results.head(5).iterrows()])}
            """
            
            st.download_button(
                label="📥 Relatório",
                data=report,
                file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
        
        # Nova análise
        if st.button("🔄 Nova Análise", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    else:
        # Página inicial
        st.info("👈 **Configure a análise na barra lateral**")
        
        with st.expander("📚 Como usar"):
            st.markdown("""
            1. **Prepare as pastas:**
               - `./files_target/` → Coloque 1 PDF (documento base)
               - `./files_pdf/` → Coloque vários PDFs para comparação
            
            2. **Selecione o documento base** na barra lateral
            
            3. **Ajuste os parâmetros do Doc2Vec:**
               - **Tamanho do Vetor**: Dimensão dos embeddings (100-200 é bom)
               - **Janela**: Contexto das palavras (5-10)
               - **Min Count**: Ignorar palavras raras (2-3)
               - **Épocas**: Iterações de treinamento (30-50)
            
            4. **Clique em 'Executar Análise'**
            
            5. **Visualize os resultados** e exporte se necessário
            """)
        
        with st.expander("🤔 Sobre o Doc2Vec"):
            st.markdown("""
            **Doc2Vec** é um algoritmo que cria representações vetoriais (embeddings) 
            de documentos inteiros, capturando seu significado semântico.
            
            **Como funciona:**
            - Transforma cada documento em um vetor de números
            - Documentos similares têm vetores próximos no espaço
            - Calcula similaridade usando cosseno entre vetores
            
            **Vantagens:**
            - Considera o contexto e ordem das palavras
            - Captura relações semânticas
            - Funciona bem com documentos de diferentes tamanhos
            """)

if __name__ == "__main__":
    main()

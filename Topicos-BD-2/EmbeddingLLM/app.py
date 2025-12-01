# app.py - VERSÃO ATUALIZADA COM width='stretch'

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
# Importar o gerenciador de modelos
from model_trainer import Doc2VecModelManager
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
FILES_PDF = PROJECT_ROOT / "files_pdf"
FILES_TARGET = PROJECT_ROOT / "files_target"

# Configurar página do Streamlit
st.set_page_config(
    page_title="Análise de Similaridade Doc2Vec",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
<style>
[data-testid="stMetricValue"] {
    font-size: 20px;
}
[data-testid="stImage"] {
    margin: 0 auto;
    display: block;
}
</style>
""",
    unsafe_allow_html=True,
)

# Configuração de estilo
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Inicializar estados da sessão
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
if 'base_pdf_path' not in st.session_state:
    st.session_state.base_pdf_path = None

class SimilarityAnalyzer:
    """Analisador de similaridade entre documentos"""
    
    @staticmethod
    def calculate_similarity_statistics(similarities):
        """Calcula estatísticas de similaridade"""
        if len(similarities) == 0:
            return {}
        
        stats_dict = {
            'Média': np.mean(similarities),
            'Mediana': np.median(similarities),
            'Desvio Padrão': np.std(similarities),
            'Mínimo': np.min(similarities),
            'Máximo': np.max(similarities),
            'Amplitude': np.max(similarities) - np.min(similarities),
        }
        
        return stats_dict
    
    @staticmethod
    def compare_documents(model_manager, base_pdf_path, pdf_files, model_params):
        """Compara documentos e retorna resultados"""
        results = {
            'arquivo': [],
            'similaridade': [],
            'paginas': [],
            'tamanho_texto': [],
            'sentencas': []
        }
        
        # Treinar modelo com documento base
        base_model = model_manager.train_model_for_document(
            base_pdf_path,
            vector_size=model_params['vector_size'],
            window=model_params['window'],
            min_count=model_params['min_count'],
            epochs=model_params['epochs']
        )
        
        if not base_model:
            return None
        
        # Extrair embedding do documento base
        base_stats = model_manager.calculate_document_stats(base_pdf_path)
        base_embedding = model_manager.infer_document_embedding(
            base_model, 
            base_stats['text']
        )
        
        if base_embedding is None:
            return None
        
        # Processar outros documentos
        for pdf_file in pdf_files:
            file_name = os.path.basename(pdf_file)
            
            # Extrair estatísticas
            doc_stats = model_manager.calculate_document_stats(pdf_file)
            if not doc_stats:
                continue
            
            # Inferir embedding
            other_embedding = model_manager.infer_document_embedding(
                base_model, 
                doc_stats['text']
            )
            
            if other_embedding is None:
                continue
            
            # Calcular similaridade
            similarity = cosine_similarity([base_embedding], [other_embedding])[0][0]
            
            # Armazenar resultados
            results['arquivo'].append(file_name)
            results['similaridade'].append(similarity)
            results['paginas'].append(doc_stats['num_pages'])
            results['tamanho_texto'].append(doc_stats['text_length'])
            results['sentencas'].append(doc_stats['num_sentences'])
        
        if not results['arquivo']:
            return None
        
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values('similaridade', ascending=False)
        
        # Calcular estatísticas
        similarities = df_results['similaridade'].values
        stats_dict = SimilarityAnalyzer.calculate_similarity_statistics(similarities)
        
        return df_results, stats_dict, base_stats

class VisualizationManager:
    """Gerencia visualizações e gráficos"""
    
    @staticmethod
    def create_radar_chart_matplotlib(df_results, base_file_name):
        """Cria gráfico de radar para top 5 documentos usando matplotlib (como no gera_embbedings.py)"""
        if len(df_results) < 3:
            return None
            
        top_n = min(5, len(df_results))
        top_docs = df_results.head(top_n)
        
        # Normalizar características para o radar chart
        features = ['similaridade', 'paginas', 'tamanho_texto', 'sentencas']
        normalized_data = []
        
        for feature in features:
            max_val = top_docs[feature].max()
            min_val = top_docs[feature].min()
            if max_val != min_val:
                normalized = (top_docs[feature] - min_val) / (max_val - min_val)
            else:
                normalized = top_docs[feature] * 0  # Todos zeros se todos forem iguais
            normalized_data.append(normalized.values)
        
        # Configurar ângulos para o radar chart
        angles = np.linspace(0, 2 * np.pi, len(features), endpoint=False).tolist()
        angles += angles[:1]  # Fechar o círculo
        
        fig, ax = plt.subplots(figsize=(12, 10), subplot_kw=dict(projection='polar'))
        
        # Plotar cada documento
        colors = plt.cm.Set2(np.linspace(0, 1, top_n))
        for i in range(top_n):
            values = [data[i] for data in normalized_data]
            values += values[:1]  # Fechar o círculo
            
            ax.plot(angles, values, 'o-', linewidth=2, 
                   label=top_docs.iloc[i]['arquivo'][:20] + '...' if len(top_docs.iloc[i]['arquivo']) > 20 else top_docs.iloc[i]['arquivo'],
                   color=colors[i])
            ax.fill(angles, values, alpha=0.1, color=colors[i])
        
        # Configurar eixos
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(features, fontsize=12)
        ax.set_ylim(0, 1)
        ax.set_title(f'Comparação Radar - Top {top_n} Documentos', fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=10)
        ax.grid(True)
        
        return fig
    
    @staticmethod
    def create_similarity_vs_textsize_matplotlib(df_results):
        """Cria gráfico de similaridade vs tamanho do texto usando matplotlib"""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Gráfico de dispersão
        scatter = ax.scatter(df_results['tamanho_texto'], df_results['similaridade'], 
                           c=df_results['similaridade'], cmap='viridis', s=100, alpha=0.7)
        
        # Adicionar labels aos pontos (para TODOS os pontos)
        for i, row in df_results.iterrows():
            ax.annotate(row['arquivo'][:15] + '...' if len(row['arquivo']) > 15 else row['arquivo'], 
                       (row['tamanho_texto'], row['similaridade']),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=8, alpha=0.7)
        
        ax.set_title('Similaridade vs Tamanho do Texto', fontsize=16, fontweight='bold')
        ax.set_xlabel('Tamanho do Texto (caracteres)', fontsize=14)
        ax.set_ylabel('Similaridade (Cosine)', fontsize=14)
        
        # Adicionar barra de cores
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Similaridade', fontsize=12)
        
        ax.grid(True, alpha=0.3)
        
        return fig
    
    @staticmethod
    def create_top_similarity_barchart_matplotlib(df_results):
        """Cria gráfico de barras horizontais para top documentos similares usando matplotlib"""
        top_10 = df_results.head(10).copy()
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Criar barras horizontais
        y_pos = np.arange(len(top_10))
        bars = ax.barh(y_pos, top_10['similaridade'], color=plt.cm.viridis(top_10['similaridade']))
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(top_10['arquivo'].apply(lambda x: x[:25] + '...' if len(x) > 25 else x), fontsize=11)
        ax.invert_yaxis()  # Mostrar o mais similar no topo
        ax.set_xlabel('Similaridade (Cosine)', fontsize=14)
        ax.set_title('Top 10 Documentos Mais Similares', fontsize=16, fontweight='bold')
        ax.set_xlim(0, 1)
        ax.grid(True, axis='x', alpha=0.3)
        
        # Adicionar valores nas barras
        for i, (bar, value) in enumerate(zip(bars, top_10['similaridade'])):
            ax.text(value + 0.01, bar.get_y() + bar.get_height()/2, 
                   f'{value:.3f}', va='center', fontsize=11, fontweight='bold')
        
        return fig
    
    @staticmethod
    def create_similarity_distribution_matplotlib(df_results):
        """Cria gráfico de distribuição das similaridades usando matplotlib"""
        fig, ax = plt.subplots(figsize=(12, 7))
        
        # Histograma
        n, bins, patches = ax.hist(df_results['similaridade'], bins=10, 
                                  edgecolor='black', alpha=0.7, color='lightcoral')
        
        ax.set_title('Distribuição das Similaridades', fontsize=16, fontweight='bold')
        ax.set_xlabel('Similaridade (Cosine)', fontsize=14)
        ax.set_ylabel('Frequência', fontsize=14)
        ax.grid(axis='y', alpha=0.3)
        
        # Adicionar linhas de média e mediana
        mean_sim = df_results['similaridade'].mean()
        median_sim = df_results['similaridade'].median()
        
        ax.axvline(mean_sim, color='red', linestyle='--', linewidth=2, label=f'Média: {mean_sim:.3f}')
        ax.axvline(median_sim, color='blue', linestyle='--', linewidth=2, label=f'Mediana: {median_sim:.3f}')
        ax.legend(fontsize=12)
        
        # Adicionar labels com os valores acima das barras
        for i in range(len(patches)):
            height = patches[i].get_height()
            if height > 0:
                x = patches[i].get_x() + patches[i].get_width() / 2
                y = height
                ax.text(x, y + 0.1, str(int(height)), ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        return fig
    
    @staticmethod
    def create_correlation_heatmap_matplotlib(df_results):
        """Cria mapa de calor de correlações usando matplotlib"""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Calcular matriz de correlação
        correlation_matrix = df_results[['similaridade', 'paginas', 'tamanho_texto', 'sentencas']].corr()
        
        # Criar heatmap
        im = ax.imshow(correlation_matrix, cmap='coolwarm', aspect='auto')
        
        # Configurar eixos
        ax.set_xticks(np.arange(len(correlation_matrix.columns)))
        ax.set_yticks(np.arange(len(correlation_matrix.columns)))
        ax.set_xticklabels(correlation_matrix.columns, rotation=45, ha="right", fontsize=12)
        ax.set_yticklabels(correlation_matrix.columns, fontsize=12)
        
        # Adicionar valores nas células
        for i in range(len(correlation_matrix.columns)):
            for j in range(len(correlation_matrix.columns)):
                # Escolher cor do texto baseado no fundo (preto para fundos claros, branco para fundos escuros)
                cell_value = correlation_matrix.iloc[i, j]
                text_color = 'black' if abs(cell_value) < 0.5 else 'white'
                text = ax.text(j, i, f'{cell_value:.2f}',
                              ha="center", va="center", color=text_color, fontweight='bold', fontsize=11)
        
        ax.set_title('Mapa de Calor - Correlações entre Variáveis', fontsize=16, fontweight='bold', pad=20)
        
        # Adicionar barra de cores
        cbar = ax.figure.colorbar(im, ax=ax)
        cbar.ax.set_ylabel('Correlação', rotation=-90, va="bottom", fontsize=12)
        
        # Remover grids
        ax.grid(False)
        
        plt.tight_layout()
        return fig

def display_dashboard_metrics(df_results, stats_dict):
    """Exibe métricas no dashboard"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📊 Similaridade Média",
            value=f"{stats_dict['Média']:.4f}",
            delta=f"Desvio: {stats_dict['Desvio Padrão']:.4f}"
        )
    
    with col2:
        st.metric(
            label="🎯 Documentos Analisados",
            value=len(df_results),
            delta=f"Mais similar: {df_results.iloc[0]['similaridade']:.4f}"
        )
    
    with col3:
        st.metric(
            label="📈 Similaridade Máxima",
            value=f"{stats_dict['Máximo']:.4f}",
            delta=f"Mínimo: {stats_dict['Mínimo']:.4f}"
        )
    
    with col4:
        cv = stats_dict['Desvio Padrão'] / stats_dict['Média'] if stats_dict['Média'] != 0 else 0
        cv_color = "normal" if cv < 0.5 else "inverse"
        st.metric(
            label="📉 Coeficiente de Variação",
            value=f"{cv:.4f}",
            delta_color=cv_color
        )

def list_pdf_files_from_folder(folder_path):
    """Lista todos os arquivos PDF em uma pasta específica"""
    import glob
    if not os.path.exists(folder_path):
        os.makedirs(folder_path, exist_ok=True)
        return []
    
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    return sorted(pdf_files)

def display_comparative_analysis(selected_doc, df_results, base_stats, base_doc):
    """Exibe análise comparativa entre o documento base e o documento selecionado"""
    st.write("#### 🔍 Análise Comparativa Detalhada")
    
    if selected_doc:
        selected_row = df_results[df_results['arquivo'] == selected_doc].iloc[0]
        
        # Criar duas colunas para comparação lado a lado
        col_base, col_selected = st.columns(2)
        
        with col_base:
            st.markdown(f"**📄 Documento Base: {base_doc}**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Tamanho", f"{base_stats['text_length']:,} caracteres")
            with col2:
                st.metric("Páginas", base_stats['num_pages'])
            with col3:
                st.metric("Sentenças", base_stats['num_sentences'])
        
        with col_selected:
            st.markdown(f"**📄 Doc. Selecionado: {selected_doc}**")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Similaridade", f"{selected_row['similaridade']:.4f}")
            with col2:
                st.metric("Páginas", int(selected_row['paginas']))
            with col3:
                st.metric("Sentenças", int(selected_row['sentencas']))

            # Classificação de similaridade
            sim = selected_row['similaridade']
            if sim > 0.7:
                classification = "Alta Similaridade"
                badge_color = "#28a745"  # Verde
                description = "Os documentos são muito semelhantes em conteúdo"
            elif sim > 0.4:
                classification = "Similaridade Média"
                badge_color = "#fd7e14"  # Laranja
                description = "Os documentos têm conteúdo relacionado mas não idêntico"
            else:
                classification = "Baixa Similaridade"
                badge_color = "#dc3545"  # Vermelho
                description = "Os documentos têm conteúdo diferente"
            
            st.markdown(
                f"""
                <div style="text-align: center; margin-top: 10px;">
                    <div style="background-color: {badge_color}; color: white; padding: 8px 15px; 
                             border-radius: 20px; font-weight: bold; display: inline-block; margin-bottom: 10px;">
                        {classification}
                    </div>
                    <p style="font-size: 0.9em; color: #666;">{description}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        # Análise adicional
        st.markdown("---")
        
        # Posição no ranking
        position = df_results[df_results['arquivo'] == selected_doc].index[0] + 1
        total = len(df_results)
        
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.markdown(f"**📊 Posição no Ranking:** #{position} de {total}")
        
        with col_info2:
            if position == 1:
                st.markdown("**🏆 Status:** Documento mais similar")
            elif position <= total * 0.2:  # Top 20%
                st.markdown("**📈 Status:** Entre os mais similares")
            elif position <= total * 0.5:  # Top 50%
                st.markdown("**📊 Status:** Similaridade média")
            else:
                st.markdown("**📉 Status:** Entre os menos similares")
        
        with col_info3:
            percentage = (total - position + 1) / total * 100
            st.markdown(f"**🎯 Percentil de Similaridade:** {percentage:.1f}%")
        
        # Gráfico de comparação
        st.write("**📈 Comparação Visual**")
        
        # Criar DataFrame para comparação
        comp_data = {
            'Documento': [base_doc, selected_doc],
            'Tamanho do Texto': [base_stats['text_length'], selected_row['tamanho_texto']],
            'Páginas': [base_stats['num_pages'], selected_row['paginas']],
            'Sentenças': [base_stats['num_sentences'], selected_row['sentencas']]
        }
        
        comp_df = pd.DataFrame(comp_data)
        
        # Normalizar para gráfico de barras
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        metrics = ['Tamanho do Texto', 'Páginas', 'Sentenças']
        titles = ['Tamanho do Texto (caracteres)', 'Número de Páginas', 'Número de Sentenças']
        
        for idx, (metric, title) in enumerate(zip(metrics, titles)):
            axes[idx].bar(comp_df['Documento'], comp_df[metric], color=['#1f77b4', '#ff7f0e'])
            axes[idx].set_title(title, fontweight='bold')
            axes[idx].set_ylabel(title)
            axes[idx].tick_params(axis='x', rotation=45)
            
            # Adicionar valores nas barras
            for i, v in enumerate(comp_df[metric]):
                axes[idx].text(i, v, f'{v:,.0f}' if metric == 'Tamanho do Texto' else f'{v}', 
                             ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        st.pyplot(fig)

def main():
    # Título e descrição
    st.write("### 📊 Análise de Similaridade de Documentos com Doc2Vec")
    st.markdown("""
    Esta aplicação utiliza o modelo Doc2Vec para analisar a similaridade entre documentos PDF.
    """)
    
    # Inicializar gerenciador de modelos
    model_manager = Doc2VecModelManager()
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Listar PDFs disponíveis na pasta files_target (documentos base)
        base_pdf_files = list_pdf_files_from_folder(FILES_TARGET)
        
        if not base_pdf_files:
            st.warning("Nenhum arquivo PDF encontrado na pasta './files_target'.")
            st.info("Adicione o documento base (PDF) na pasta './files_target' para começar a análise.")
            return
        
        # Selecionar documento base
        st.subheader("🎯 Documento Base")
        base_doc_options = [os.path.basename(f) for f in base_pdf_files]
        base_doc = st.selectbox(
            "Selecione o documento base para comparação",
            base_doc_options
        )
        
        # Parâmetros do modelo
        st.subheader("🤖 Parâmetros do Modelo")
        
        col1, col2 = st.columns(2)
        with col1:
            vector_size = st.slider("Tamanho do Vetor", 50, 300, 100)
            window = st.slider("Janela de Contexto", 2, 15, 5)
        
        with col2:
            min_count = st.slider("Frequência Mínima", 1, 10, 2)
            epochs = st.slider("Épocas de Treinamento", 20, 100, 40)
        
        model_params = {
            'vector_size': vector_size,
            'window': window,
            'min_count': min_count,
            'epochs': epochs
        }
        
        # Botão para iniciar análise
        analyze_button = st.button("🔍 Iniciar Análise", type="primary", width='stretch')
        
    comparison_pdf_files = list_pdf_files_from_folder(FILES_PDF)
    
    # Processar análise quando o botão for clicado
    if analyze_button:
        # Verificar se há documentos para comparação
        if not comparison_pdf_files:
            st.error("Nenhum documento encontrado para comparação na pasta './files_pdf'.")
            st.info("Adicione pelo menos um arquivo PDF na pasta './files_pdf' para comparação.")
            return
        
        # Encontrar arquivo base
        base_pdf_path = next((f for f in base_pdf_files if os.path.basename(f) == base_doc), None)
        
        if not base_pdf_path:
            st.error("Documento base não encontrado!")
            return
        
        with st.spinner("Processando documentos..."):
            # Analisar similaridades
            analyzer = SimilarityAnalyzer()
            results = analyzer.compare_documents(
                model_manager, 
                base_pdf_path, 
                comparison_pdf_files, 
                model_params
            )
            
            if results is None:
                st.error("Não foi possível realizar a análise.")
                return
            
            df_results, stats_dict, base_stats = results
            
            # Armazenar resultados no session state
            st.session_state.analysis_complete = True
            st.session_state.df_results = df_results
            st.session_state.stats_dict = stats_dict
            st.session_state.base_stats = base_stats
            st.session_state.base_doc = base_doc
            st.session_state.base_pdf_path = base_pdf_path
            
            st.success("✅ Análise concluída com sucesso!")
    
    # Mostrar resultados se a análise foi concluída (mesmo em recarregamentos)
    if st.session_state.analysis_complete:
        df_results = st.session_state.df_results
        stats_dict = st.session_state.stats_dict
        base_stats = st.session_state.base_stats
        base_doc = st.session_state.base_doc
        base_pdf_path = st.session_state.base_pdf_path
        
        # Mostrar informações do documento base
        st.write(f"#### 📄 Doc. Base: {base_doc}")
        
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            st.metric("Tamanho", f"{base_stats['text_length']:,} caracteres")
        with col2:
            st.metric("Páginas", base_stats['num_pages'])
        with col3:
            st.metric("Sentenças", base_stats['num_sentences'])
        
        # Dashboard de métricas
        st.write("#### 📊 Dashboard de Resultados")
        display_dashboard_metrics(df_results, stats_dict)
        
        # Tabela de resultados
        st.write("#### 📋 Tabela de Similaridades")
        display_df = df_results.copy()
        display_df['similaridade'] = display_df['similaridade'].map('{:.4f}'.format)
        display_df['tamanho_texto'] = display_df['tamanho_texto'].map('{:,}'.format)
        display_df['paginas'] = display_df['paginas'].astype(int)
        display_df['sentencas'] = display_df['sentencas'].astype(int)
        
        st.dataframe(
            display_df,
            column_config={
                "arquivo": "Documento",
                "similaridade": st.column_config.NumberColumn(
                    "Similaridade",
                    help="Similaridade cosine com o documento base",
                    format="%.4f"
                ),
                "paginas": "Páginas",
                "tamanho_texto": "Caracteres",
                "sentencas": "Sentenças"
            },
            width='stretch',
            hide_index=True
        )
        
        # Visualizações
        st.write("#### 📈 Visualizações")
        
        # Inicializar gerenciador de visualizações
        viz_manager = VisualizationManager()
        
        # Container para os gráficos
        col_left, col_center, col_right = st.columns([1, 8, 1])
        
        with col_center:
            # 1. Gráfico de Radar (Matplotlib)
            if len(df_results) >= 3:
                radar_fig = viz_manager.create_radar_chart_matplotlib(df_results, base_doc)
                if radar_fig:
                    st.pyplot(radar_fig, width='stretch')
                else:
                    st.info("Gráfico de radar disponível apenas para 3 ou mais documentos")
            else:
                st.info("Gráfico de radar disponível apenas para 3 ou mais documentos")
            
            # 2. Gráfico Similaridade vs Tamanho do Texto (Matplotlib)
            scatter_fig = viz_manager.create_similarity_vs_textsize_matplotlib(df_results)
            st.pyplot(scatter_fig, width='stretch')
            
            # 3. Gráfico de Barras Horizontais Top 10 (Matplotlib)
            top_fig = viz_manager.create_top_similarity_barchart_matplotlib(df_results)
            st.pyplot(top_fig, width='stretch')
            
            # 4. Gráfico de Distribuição (Matplotlib)
            dist_fig = viz_manager.create_similarity_distribution_matplotlib(df_results)
            st.pyplot(dist_fig, width='stretch')
            
            # 5. Mapa de Calor de Correlações (Matplotlib)
            heatmap_fig = viz_manager.create_correlation_heatmap_matplotlib(df_results)
            st.pyplot(heatmap_fig, width='stretch')
        
        # Análise Detalhada por Documento
        st.write("#### 🔍 Análise Detalhada por Documento")
        
        selected_doc = st.selectbox(
            "Selecione um documento para análise comparativa detalhada",
            df_results['arquivo'].tolist(),
            key="detailed_analysis_selectbox"
        )
        
        # Exibir análise comparativa
        if selected_doc:
            display_comparative_analysis(selected_doc, df_results, base_stats, base_doc)
        
        # Exportar resultados
        st.write("#### 💾 Exportar Resultados")
        
        col1, col2, col3 = st.columns(3)
        
        # Converter DataFrame para CSV
        csv = df_results.to_csv(index=False).encode('utf-8')
        
        # Converter DataFrame para Excel
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_results.to_excel(writer, sheet_name='Resultados', index=False)
            # Adicionar estatísticas
            stats_df = pd.DataFrame(list(stats_dict.items()), columns=['Estatística', 'Valor'])
            stats_df.to_excel(writer, sheet_name='Estatísticas', index=False)
        excel_buffer.seek(0)
        
        with col1:
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"similaridade_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            st.download_button(
                label="📥 Download Excel",
                data=excel_buffer,
                file_name=f"similaridade_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col3:
            # Gerar relatório em texto
            report_text = f"""
            RELATÓRIO DE ANÁLISE DE SIMILARIDADE
            Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            Documento base: {base_doc}
            Localização do documento base: {base_pdf_path}
            Total de documentos comparados: {len(df_results)}
            
            ESTATÍSTICAS:
            {chr(10).join([f'{k}: {v:.4f}' if isinstance(v, float) else f'{k}: {v}' for k, v in stats_dict.items()])}
            
            RANKING:
            {chr(10).join([f'{i+1}. {row["arquivo"]}: {row["similaridade"]:.4f}' for i, row in df_results.iterrows()])}
            """
            
            st.download_button(
                label="📥 Download Relatório",
                data=report_text,
                file_name=f"relatorio_similaridade_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
            
        # Botão para nova análise
        if st.button("🔄 Realizar Nova Análise", type="secondary"):
            # Limpar session state
            for key in ['analysis_complete', 'df_results', 'stats_dict', 'base_stats', 'base_doc', 'base_pdf_path']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
    else:
        # Tela inicial
        st.info("👈 **Configure os parâmetros na barra lateral e clique em 'Iniciar Análise'**")
        
        # Exemplo de como funciona
        st.markdown("---")
        st.write("#### 🎯 Como Funciona")
        
        steps_col1, steps_col2, steps_col3, steps_col4 = st.columns(4)
        
        with steps_col1:
            st.markdown("""
            **1. Preparação**  
            - 1 PDF em `./files_target`  
            - PDFs em `./files_pdf`
            """)
        
        with steps_col2:
            st.markdown("""
            **2. Configuração**  
            Selecione documento base e ajuste parâmetros
            """)
        
        with steps_col3:
            st.markdown("""
            **3. Processamento**  
            Treinamento e análise automática
            """)
        
        with steps_col4:
            st.markdown("""
            **4. Resultados**  
            Visualize gráficos e estatísticas
            """)
        
        # Informações técnicas
        with st.expander("ℹ️ Informações Técnicas"):
            st.markdown("""
            **Tecnologias utilizadas:**
            - **Doc2Vec**: Modelo de embeddings para documentos
            - **Streamlit**: Interface web interativa
            - **Matplotlib & Seaborn**: Visualizações gráficas
            - **Scikit-learn**: Cálculo de similaridade cosine
            - **NLTK**: Processamento de linguagem natural
            
            **Gráficos disponíveis:**
            - Comparação Radar - Top 5 Documentos
            - Similaridade vs Tamanho do Texto
            - Top 10 Documentos Mais Similares
            - Distribuição das Similaridades
            - Mapa de Calor de Correlações
            
            **Pastas:**
            - `./files_target/`: Documento base
            - `./files_pdf/`: Documentos para comparação
            """)

if __name__ == "__main__":
    main()

import streamlit as st
import paho.mqtt.client as mqtt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import time
import threading
from scipy import interpolate
import logging
import pytz

css = '''
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size:1.2rem;
    }

    .block-container {
        padding-top: 1.8rem; /* Altere para 0rem se quiser sem espaço nenhum */
        padding-bottom: 0rem;
        margin-top: 0rem;
    }

    h2 {
        font-size: 30px !important;
        padding-top: 0rem;
        margin-top: 0rem !important;
    }

    h3 {
        font-size: 20px !important;
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }

    /* Change background and font color of tabs */
    .stTabs [data-baseweb="tab-list"] {gap: 6px;}
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #F0F2F6;
        border-radius: 3px 3px 2px 2px;
        padding-top: 5px;
        padding-bottom: 5px;
    }
    /* Style the active tab */
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        color: #FF4B4B;
    }
    
</style>
'''
st.markdown(css, unsafe_allow_html=True)

# ================= CONFIGURAÇÃO =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
TOPIC_DATA = "cfe-hydro/data"

# Fuso horário local
LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo')  # Ajuste para seu fuso horário

st.set_page_config(
    page_title="Dashboard CFE-HYDRO",
    page_icon="🌱",
    layout="wide"
)

# ================= CLASSES DE INTERPOLAÇÃO =================
class InterpoladorSeletivo:
    """Implementa interpolação seletiva conforme protocolo CFE-HYDRO"""
    
    @staticmethod
    def interpolar(x_known, y_known, x_new, metodo='linear', sensor_type=None):
        """Aplica interpolação baseada no tipo de sensor"""
        if len(x_known) < 2:
            return np.full_like(x_new, y_known[0] if len(y_known) > 0 else np.nan)
        
        x_known = np.asarray(x_known, dtype=np.float64)
        y_known = np.asarray(y_known, dtype=np.float64)
        x_new = np.asarray(x_new, dtype=np.float64)
        
        if metodo == 'logarithmic':  # pH
            y_interp = np.interp(x_new, x_known, y_known)
            return np.clip(y_interp, 0, 14)
        
        elif metodo == 'polynomial' and sensor_type in ['ec', 'do']:  # EC e OD
            try:
                # Spline cúbico para EC e OD
                tck = interpolate.splrep(x_known, y_known, s=0, k=min(3, len(x_known)-1))
                y_interp = interpolate.splev(x_new, tck, der=0)
                
                # Limites físicos
                if sensor_type == 'ec':
                    return np.clip(y_interp, 0, 20.0)
                elif sensor_type == 'do':
                    return np.clip(y_interp, 0, 20.0)
                    
            except Exception:
                # Fallback para interpolação linear
                y_interp = np.interp(x_new, x_known, y_known)
                return np.maximum(y_interp, 0)
        
        else:  # Temperatura e fallback
            return np.interp(x_new, x_known, y_known)

# ================= GESTÃO DE DADOS =================
class GerenciadorDados:
    """Gerencia armazenamento e processamento dos dados dos sensores"""
    
    def __init__(self):
        self.data_lock = threading.Lock()
        self.sensor_data = {tipo: pd.DataFrame(columns=['timestamp', 'value', 'interpolation']) 
                          for tipo in ['temperature', 'ph', 'ec', 'do']}
        self.messages_received = 0
        self.last_message_time = None
    
    def adicionar_ponto(self, sensor_type, timestamp, value, interpolation_type):
        """Adiciona um novo ponto de dados"""
        try:
            with self.data_lock:
                df = self.sensor_data[sensor_type]
                new_row = pd.DataFrame({
                    'timestamp': [timestamp],
                    'value': [float(value)],
                    'interpolation': [interpolation_type]
                })
                self.sensor_data[sensor_type] = pd.concat([df, new_row], ignore_index=True)
                
                # Manter apenas últimos 1000 pontos
                if len(self.sensor_data[sensor_type]) > 1000:
                    self.sensor_data[sensor_type] = self.sensor_data[sensor_type].iloc[-1000:]
                
                self.messages_received += 1
                self.last_message_time = datetime.now()
                
        except (ValueError, TypeError) as e:
            logger.error(f"Erro ao adicionar ponto para {sensor_type}: {e}")
    
    def obter_dados_interpolados(self, sensor_type, interval_seconds=60):
        """Obtém dados interpolados em intervalo regular"""
        with self.data_lock:
            df = self.sensor_data[sensor_type].copy()
        
        if df.empty or len(df) < 2:
            return pd.DataFrame(columns=['datetime', 'value', 'interpolation', 'is_interpolated'])
        
        # Converter timestamp para datetime - detectar se está em segundos ou milissegundos
        if not df.empty:
            sample_timestamp = float(df['timestamp'].iloc[0])
            
            if sample_timestamp > 1e12:  # Provavelmente em milissegundos
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(LOCAL_TIMEZONE)
            else:  # Provavelmente em segundos
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert(LOCAL_TIMEZONE)
        
        df = df.sort_values('datetime')
        
        start_time = df['datetime'].min()
        end_time = df['datetime'].max()
        regular_times = pd.date_range(start=start_time, end=end_time, freq=f'{interval_seconds}S', tz=LOCAL_TIMEZONE)
        
        # Converter para milissegundos para interpolação
        x_known = df['datetime'].astype(np.int64) // 10**6
        y_known = df['value'].values
        x_new = regular_times.astype(np.int64) // 10**6
        
        metodo_interpolacao = df['interpolation'].iloc[0] if not df['interpolation'].empty else 'linear'
        
        try:
            y_new = InterpoladorSeletivo.interpolar(
                x_known, y_known, x_new, metodo_interpolacao, sensor_type
            )
        except Exception as e:
            logger.error(f"Erro na interpolação: {e}")
            y_new = np.interp(x_new, x_known, y_known)
        
        # Criar DataFrame interpolado
        interpolated_df = pd.DataFrame({
            'datetime': regular_times,
            'value': y_new,
            'interpolation': metodo_interpolacao,
            'is_interpolated': True
        })
        
        return interpolated_df.dropna(subset=['value'])
    
    def obter_dados_brutos(self, sensor_type, horas=24):
        """Obtém dados brutos das últimas N horas"""
        with self.data_lock:
            df = self.sensor_data[sensor_type].copy()
        
        if df.empty:
            return pd.DataFrame(columns=['datetime', 'value', 'interpolation', 'is_interpolated'])
        
        # Converter timestamp para datetime - detectar se está em segundos ou milissegundos
        if not df.empty:
            sample_timestamp = float(df['timestamp'].iloc[0])
            
            if sample_timestamp > 1e12:  # Provavelmente em milissegundos
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(LOCAL_TIMEZONE)
            else:  # Provavelmente em segundos
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert(LOCAL_TIMEZONE)
        
        cutoff = datetime.now(LOCAL_TIMEZONE) - timedelta(hours=horas)
        filtered_df = df[df['datetime'] >= cutoff].copy()
        filtered_df['is_interpolated'] = False
        
        return filtered_df
    
    def obter_dados_combinados(self, sensor_type, horas=24, interval_seconds=60):
        """Combina dados brutos e interpolados"""
        raw_data = self.obter_dados_brutos(sensor_type, horas)
        interpolated_data = self.obter_dados_interpolados(sensor_type, interval_seconds)
        
        combined = pd.concat([raw_data, interpolated_data], ignore_index=True)
        return combined.sort_values('datetime', ascending=False)
    
    def obter_valor_mais_recente(self, sensor_type):
        """Obtém o valor mais recente de um sensor"""
        with self.data_lock:
            df = self.sensor_data[sensor_type]
        
        if df.empty:
            return None
        
        df_sorted = df.sort_values('timestamp')
        return df_sorted['value'].iloc[-1] if not df_sorted.empty else None
    
    def tem_dados(self):
        """Verifica se há algum dado disponível"""
        return any(len(df) > 0 for df in self.sensor_data.values())

# ================= CLIENTE MQTT =================
class ClienteMQTT:
    """Cliente MQTT para receber dados dos sensores"""
    
    def __init__(self, gerenciador_dados):
        self.gerenciador_dados = gerenciador_dados
        client_id = f"cfe-hydro-dashboard-{int(time.time())}"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        self.connection_error = None
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback chamado quando conectado ao broker"""
        if rc == 0:
            self.connected = True
            self.connection_error = None
            logger.info("✅ Conectado ao broker MQTT")
            client.subscribe([(TOPIC_DATA, 0)])
        else:
            self.connected = False
            self.connection_error = f"Código de erro: {rc}"
            logger.error(f"❌ Falha na conexão MQTT: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback chamado quando desconectado do broker"""
        self.connected = False
        if rc != 0:
            self.connection_error = "Conexão perdida. Tentando reconectar..."
            logger.warning(f"Desconectado inesperadamente do broker MQTT: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback chamado quando uma mensagem é recebida"""
        try:
            payload = msg.payload.decode('utf-8')
            logger.info(f"Mensagem recebida no tópico {msg.topic}: {payload[:100]}...")
            data = json.loads(payload)
            
            if 'readings' in data:
                self._processar_dados_sensores(data['readings'])
                
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
    
    def _processar_dados_sensores(self, readings):
        """Processa leituras dos sensores"""
        leituras_adicionadas = 0
        
        for reading in readings:
            sensor_type = reading.get('sensor_type')
            value = reading.get('value')
            timestamp = reading.get('timestamp')
            interpolation = reading.get('interpolation', 'linear')
            
            if sensor_type and value is not None and timestamp:
                # VERIFICAÇÃO CRÍTICA: Se timestamp está em segundos, converter para milissegundos
                # Se o timestamp for menor que 1.7e9 (2023), provavelmente está em segundos
                if timestamp < 2e9:  # Timestamp em segundos (ex: 1770430813)
                    timestamp = int(timestamp * 1000)  # Converter para milissegundos
                    logger.info(f"Timestamp convertido: {timestamp} (de segundos para ms)")
                
                # Ajustar timestamp se for muito antigo
                current_time_ms = int(time.time() * 1000)
                if timestamp < (current_time_ms - 86400000):  # Mais de 24 horas atrás
                    logger.warning(f"Timestamp muito antigo: {timestamp}. Ajustando para atual.")
                    timestamp = current_time_ms
                
                self.gerenciador_dados.adicionar_ponto(sensor_type, timestamp, value, interpolation)
                leituras_adicionadas += 1
        
        if leituras_adicionadas > 0:
            logger.info(f"Processadas {leituras_adicionadas} leituras")
    
    def conectar(self):
        """Conecta ao broker MQTT"""
        try:
            logger.info(f"Tentando conectar ao broker {MQTT_BROKER}:{MQTT_PORT}...")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            # Aguardar um pouco para a conexão ser estabelecida
            time.sleep(2)
            
            if not self.connected:
                self.connection_error = "Tempo esgotado aguardando conexão"
                logger.warning("Conexão não estabelecida após 2 segundos")
                
        except Exception as e:
            self.connected = False
            self.connection_error = str(e)
            logger.error(f"Erro na conexão MQTT: {e}")
    
    def desconectar(self):
        """Desconecta do broker MQTT"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info("Desconectado do broker MQTT")
        except Exception as e:
            logger.error(f"Erro ao desconectar: {e}")

# ================= FUNÇÕES AUXILIARES =================
def criar_grafico_sensor(dados_brutos, dados_interpolados, nome_sensor, unidade, cor):
    """Cria gráfico para um sensor com dados brutos e interpolados"""
    fig = go.Figure()
    
    # Dados interpolados (linha tracejada)
    if not dados_interpolados.empty:
        fig.add_trace(go.Scatter(
            x=dados_interpolados['datetime'],
            y=dados_interpolados['value'],
            mode='lines+markers',
            name=f'{nome_sensor} (Interpolado)',
            line=dict(color=cor, width=2, dash='dash'),
            marker=dict(size=6, color=cor),
            opacity=0.8
        ))
    
    # Dados brutos (linha contínua)
    if not dados_brutos.empty:
        fig.add_trace(go.Scatter(
            x=dados_brutos['datetime'],
            y=dados_brutos['value'],
            mode='lines+markers',
            name=f'{nome_sensor} (Recebido)',
            line=dict(color=cor, width=3),
            marker=dict(size=8, color=cor),
            opacity=0.9
        ))
    
    fig.update_layout(
        title=f"{nome_sensor} - Evolução Temporal",
        xaxis_title="Tempo",
        yaxis_title=f"{nome_sensor} ({unidade})",
        hovermode="x unified",
        height=400,
        margin=dict(l=20, r=20, t=50, b=30),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    
    fig.update_traces(line_shape='spline')
    return fig

def informacoes_sensor(sensor_type):
    """Retorna informações sobre cada sensor"""
    info = {
        'temperature': {
            'nome': 'Temperatura',
            'unidade': '°C',
            'cor': '#FF6B6B',
            'faixa_otima': (18, 25)
        },
        'ph': {
            'nome': 'pH',
            'unidade': '',
            'cor': '#4ECDC4',
            'faixa_otima': (5.5, 6.5)
        },
        'ec': {
            'nome': 'Condutividade Elétrica',
            'unidade': 'mS/cm',
            'cor': '#45B7D1',
            'faixa_otima': (1.0, 3.0)
        },
        'do': {
            'nome': 'Oxigênio Dissolvido',
            'unidade': 'mg/L',
            'cor': '#96CEB4',
            'faixa_otima': (5.0, 8.0)
        }
    }
    return info.get(sensor_type, {})

def exibir_tabela_dados(dados_combinados, info_sensor):
    """Exibe tabela com dados recebidos e interpolados"""
    if dados_combinados.empty:
        st.info("Nenhum dado disponível para exibir")
        return
    
    # Preparar DataFrame para exibição
    df_exibicao = dados_combinados.copy()
    df_exibicao = df_exibicao.sort_values('datetime', ascending=False)
    df_exibicao = df_exibicao.reset_index(drop=True)
    
    # Criar coluna ID (mais recente = ID maior)
    total_linhas = len(df_exibicao)
    df_exibicao.insert(0, 'ID', range(total_linhas, 0, -1))
    
    # Formatar colunas
    df_exibicao['Data/Hora'] = df_exibicao['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df_exibicao['Valor'] = df_exibicao['value'].apply(lambda x: f"{float(x):.3f}" if pd.notnull(x) else "--")
    df_exibicao['Tipo'] = df_exibicao['is_interpolated'].apply(lambda x: 'Interpolado' if x else 'Recebido')
    
    # Selecionar e ordenar colunas
    df_exibicao = df_exibicao[['ID', 'Data/Hora', 'Valor', 'interpolation', 'Tipo']]
    df_exibicao.columns = ['ID', 'Data/Hora', 'Valor', 'Interpolação', 'Tipo']
    
    # Exibir tabela com formatação
    st.dataframe(
        df_exibicao.style.apply(
            lambda x: ['background-color: #E8F5E9' if x['Tipo'] == 'Recebido' else 'background-color: #FFF3E0' for _ in x],
            axis=1
        ),
        use_container_width=True,
        height=400
    )
    
    # Legenda
#    col1, col2 = st.columns(2)
#    with col1:
#        st.markdown("📥 **Dados Recebidos do Broker**", unsafe_allow_html=True)
#    with col2:
#        st.markdown("📊 **Dados Interpolados**", unsafe_allow_html=True)

    # LEGENDAS COM BOXES COLORIDOS - APENAS AS LEGENDAS
    col1, col2, col3, col4 = st.columns(4)
    
    with col3:
        # Box para Dados Recebidos
        st.markdown(
            '''
            <div style="
                background-color: #E8F5E9; 
                padding: 3px; 
                border-radius: 8px; 
                border: 0px solid #4CAF50; 
                text-align: center;
                display: flex;
                align-items: right;
                justify-content: center;
                min-height: 30px;
                margin: 2px 0;
                width: 100%;
            ">
                <div style="font-size: 16px; font-weight: bold;">
                    📥 Dados Recebidos do Broker
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )
    
    with col4:
        # Box para Dados Interpolados
        st.markdown(
            '''
            <div style="
                background-color: #FFF3E0; 
                padding: 3px; 
                border-radius: 8px; 
                border: 0px solid #FF9800; 
                text-align: center;
                display: flex;
                align-items: right;
                justify-content: center;
                min-height: 30px;
                margin: 2px 0;
                width: 100%;
            ">
                <div style="font-size: 16px; font-weight: bold;">
                    📊 Dados Interpolados
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        

# ================= APLICAÇÃO PRINCIPAL =================
def main():
    st.title("🌱 CFE-HYDRO - Monitoramento")
    st.markdown("Sistema de monitoramento com **interpolação seletiva** usando o protocolo CFE-HYDRO.")
    
    # Inicializar estado da sessão
    if 'gerenciador_dados' not in st.session_state:
        st.session_state.gerenciador_dados = GerenciadorDados()
        st.session_state.cliente_mqtt = ClienteMQTT(st.session_state.gerenciador_dados)
        st.session_state.ultima_atualizacao = datetime.now()
        st.session_state.intervalo_atualizacao = 30
    
    # Inicializar conexão MQTT (se ainda não foi feita)
    if 'mqtt_conectado' not in st.session_state:
        st.session_state.mqtt_conectado = False
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Status MQTT
        st.subheader("📡 Status do Sistema")
        
        # Verificar e exibir status da conexão
        if hasattr(st.session_state.cliente_mqtt, 'connected') and st.session_state.cliente_mqtt.connected:
            st.success("✅ Conectado ao broker MQTT")
            st.metric("Mensagens", st.session_state.gerenciador_dados.messages_received)
        else:
            st.error("❌ Desconectado do broker MQTT")
            
            # Mostrar erro detalhado se disponível
            if hasattr(st.session_state.cliente_mqtt, 'connection_error') and st.session_state.cliente_mqtt.connection_error:
                st.warning(f"Erro: {st.session_state.cliente_mqtt.connection_error}")
            
            # Botão para tentar conexão
            if st.button("🔗 Conectar ao MQTT"):
                with st.spinner("Conectando ao broker MQTT..."):
                    st.session_state.cliente_mqtt.conectar()
                    st.rerun()
        
        # st.divider()
        
        # Configurações
        st.subheader("👁️ Configurações de Visualização")
        
        st.session_state.intervalo_atualizacao = st.slider(
            "Intervalo de atualização (segundos)", 5, 60, 60,
            help="Intervalo para atualizar automaticamente os gráficos"
        )
        
        horas_visao = st.slider(
            "Período visualizado (horas)", 1, 72, 1,
            help="Quantas horas de dados mostrar nos gráficos"
        )
        
        intervalo_interpolacao = st.slider(
            "Intervalo de Interpolação (segundos)", 10, 300, 20, step=5,
            help="Intervalo para cálculo dos pontos interpolados"
        )
        
        # Botão para limpar dados
        if st.button("🧹 Limpar Todos os Dados"):
            st.session_state.gerenciador_dados = GerenciadorDados()
            st.success("Dados limpos com sucesso!")
            st.rerun()

        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")
        if hasattr(st.session_state.cliente_mqtt, 'connected'):
            status = "✅ Conectado" if st.session_state.cliente_mqtt.connected else "❌ Desconectado"
            st.caption(f"Status MQTT: {status}")
            st.caption(f"Atualização automática: {st.session_state.intervalo_atualizacao}s")

    # Métricas em tempo real
    st.header("📈 Últimos valores recebidos")
    colunas = st.columns(4)
    valores_recentes = {}
    
    for idx, sensor_type in enumerate(['temperature', 'ph', 'ec', 'do']):
        with colunas[idx]:
            info = informacoes_sensor(sensor_type)
            valor = st.session_state.gerenciador_dados.obter_valor_mais_recente(sensor_type)
            valores_recentes[sensor_type] = valor
            
            if valor is not None:
                faixa_min, faixa_max = info['faixa_otima']
                dentro_faixa = faixa_min <= valor <= faixa_max
                icone = "✅" if dentro_faixa else "⚠️"
                
                st.metric(
                    label=f"{info['nome']} {icone}",
                    value=f"{valor:.2f}{info['unidade']}",
                    help=f"Faixa ótima: {faixa_min}-{faixa_max}{info['unidade']}"
                )
            else:
                st.metric(label=info['nome'], value="--")
    
    # Verificar se há dados
    if not st.session_state.gerenciador_dados.tem_dados():
        # Tentar conectar automaticamente se não estiver conectado
        if not hasattr(st.session_state.cliente_mqtt, 'connected') or not st.session_state.cliente_mqtt.connected:
            st.warning("""
            ⚠️ **Não conectado ao broker MQTT!**
            
            Clique no botão "Conectar ao MQTT" na barra lateral para estabelecer a conexão.
            
            **Detalhes do broker:**
            - Servidor: `test.mosquitto.org`
            - Porta: `1883`
            - Tópico: `cfe-hydro/data`
            """)
        else:
            st.info("""
            📡 **Conectado ao broker MQTT!**
            
            Aguardando dados do dispositivo...
            
            Certifique-se de que o dispositivo está enviando dados para o tópico:
            **`cfe-hydro/data`**
            """)
        
        # Mostrar status detalhado
        with st.expander("🔍 Status Detalhado"):
            st.write("**Status MQTT:**")
            st.write(f"- Conectado: {st.session_state.cliente_mqtt.connected if hasattr(st.session_state.cliente_mqtt, 'connected') else 'Não inicializado'}")
            if hasattr(st.session_state.cliente_mqtt, 'connection_error') and st.session_state.cliente_mqtt.connection_error:
                st.write(f"- Erro: {st.session_state.cliente_mqtt.connection_error}")
            st.write(f"- Broker: {MQTT_BROKER}:{MQTT_PORT}")
            st.write(f"- Tópico inscrito: {TOPIC_DATA}")
            
            st.write("**Dados disponíveis:**")
            for sensor_type in ['temperature', 'ph', 'ec', 'do']:
                info = informacoes_sensor(sensor_type)
                count = len(st.session_state.gerenciador_dados.sensor_data[sensor_type])
                st.write(f"- {info['nome']}: {count} pontos")
        
        return
    
    # Gráficos (só mostrar se tiver dados)
    if st.session_state.gerenciador_dados.tem_dados():
        st.header("📊 Evolução Temporal dos Parâmetros")
        abas = st.tabs(["🌡️ Temperatura", "⚗️ pH", "⚡ Condutividade", "💧 Oxigênio"])
        
        for aba, sensor_type in zip(abas, ['temperature', 'ph', 'ec', 'do']):
            with aba:
                info = informacoes_sensor(sensor_type)
                
                # Obter dados
                dados_brutos = st.session_state.gerenciador_dados.obter_dados_brutos(sensor_type, horas_visao)
                dados_interpolados = st.session_state.gerenciador_dados.obter_dados_interpolados(
                    sensor_type, intervalo_interpolacao
                )
                
                if not dados_brutos.empty or not dados_interpolados.empty:
                    # Criar gráfico
                    fig = criar_grafico_sensor(
                        dados_brutos, dados_interpolados, 
                        info['nome'], info['unidade'], info['cor']
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Estatísticas
                    if not dados_brutos.empty:
                        valores_limpos = dados_brutos['value'].dropna()
                        if len(valores_limpos) > 0:
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Média", f"{valores_limpos.mean():.2f}{info['unidade']}")
                            col2.metric("Mínimo", f"{valores_limpos.min():.2f}{info['unidade']}")
                            col3.metric("Máximo", f"{valores_limpos.max():.2f}{info['unidade']}")
                    
                    # Tabela de dados
                    with st.expander("📋 Ver Dados Recebidos e Interpolados"):
                        dados_combinados = st.session_state.gerenciador_dados.obter_dados_combinados(
                            sensor_type, horas_visao, intervalo_interpolacao
                        )
                        exibir_tabela_dados(dados_combinados, info)
                else:
                    st.info(f"Aguardando dados do sensor {info['nome']}...")
        
        # Análise da qualidade
        if any(v is not None for v in valores_recentes.values()):
            st.header("🔍 Análise Qualitativa da Interpolação")
            colunas = st.columns(5)
            qualidades = []
            
            for idx, sensor_type in enumerate(['temperature', 'ph', 'ec', 'do']):
                with colunas[idx]:
                    info = informacoes_sensor(sensor_type)
                    valor = valores_recentes[sensor_type]
                    
                    if valor is not None:
                        faixa_min, faixa_max = info['faixa_otima']
                        
                        if valor < faixa_min:
                            qualidade = max(0, (valor / faixa_min) * 100)
                        elif valor > faixa_max:
                            excesso = ((valor - faixa_max) / faixa_max) * 100
                            qualidade = max(0, 100 - excesso)
                        else:
                            qualidade = 100
                        
                        qualidade = max(0, min(100, qualidade))
                        qualidades.append(qualidade)
                        
                        # Barra de progresso
                        cor = "green" if qualidade >= 80 else "orange" if qualidade >= 60 else "red"
                        st.progress(qualidade / 100)
                        st.caption(f"{info['nome']}: {qualidade:.1f}% ótimo")
            
            # Média das qualidades
            with colunas[4]:
                if qualidades and len(qualidades) == 4:
                    media_qualidade = sum(qualidades) / len(qualidades)
                    cor = "green" if media_qualidade >= 80 else "orange" if media_qualidade >= 60 else "red"
                    st.progress(media_qualidade / 100)
                    st.caption(f"Acertividade Média: {media_qualidade:.1f}%")
                else:
                    st.progress(0)
                    st.caption("Acertividade Média: Aguardando dados...")
    
    # Atualização automática
    tempo_desde_atualizacao = (datetime.now() - st.session_state.ultima_atualizacao).seconds
    if tempo_desde_atualizacao >= st.session_state.intervalo_atualizacao:
        st.session_state.ultima_atualizacao = datetime.now()
        st.rerun()
    
#    with st.sidebar:
#        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")
#        if hasattr(st.session_state.cliente_mqtt, 'connected'):
#            status = "✅ Conectado" if st.session_state.cliente_mqtt.connected else "❌ Desconectado"
#            st.caption(f"Status MQTT: {status}")
#            st.caption(f"Atualização automática: {st.session_state.intervalo_atualizacao}s")

if __name__ == "__main__":
    main()

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
import socket
from streamlit_autorefresh import st_autorefresh

# ==================== CONFIGURAÇÃO DE LOG ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== CONFIGURAÇÕES PADRÃO ====================
DEFAULT_BROKER = "test.mosquitto.org"
DEFAULT_PORT = 1883
TOPIC_DATA = "cfe-hydro/data"
LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo')

st.set_page_config(
    page_title="Dashboard CFE-HYDRO",
    page_icon="🌱",
    layout="wide"
)

# ==================== CSS ====================
css = '''
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size:1.2rem; }
    .block-container { padding-top: 1.5rem; padding-bottom: 0rem; margin-top: 0rem; }
    h1 { margin-top: 0rem !important; padding-top: 0rem;}
    h2 { font-size: 30px !important; padding-top: 0rem; margin-top: 0rem !important; }
    h3 { font-size: 20px !important; padding-top: 0rem !important; margin-top: 0rem !important; }
    .stTabs [data-baseweb="tab-list"] {gap: 6px;}
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        min-width: 150px;
        background-color: #F0F2F6;
        border-radius: 3px 3px 2px 2px;
        padding-top: 3px;
        padding-bottom: 3px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        color: #FF4B4B;
    }
</style>
'''
st.markdown(css, unsafe_allow_html=True)

# ==================== INTERPOLADOR ====================
class InterpoladorSeletivo:
    @staticmethod
    def interpolar(x_known, y_known, x_new, metodo='linear'):
        if len(x_known) < 2:
            return np.full_like(x_new, y_known[0] if len(y_known) > 0 else np.nan)
        
        x_known = np.asarray(x_known, dtype=np.float64)
        y_known = np.asarray(y_known, dtype=np.float64)
        x_new = np.asarray(x_new, dtype=np.float64)
        
        if metodo == 'logarithmic':
            min_x = x_known.min()
            x_known_adj = x_known - min_x + 1
            x_new_adj = x_new - min_x + 1
            log_x_known = np.log(x_known_adj)
            log_x_new = np.log(x_new_adj)
            y_interp = np.interp(log_x_new, log_x_known, y_known)
            return np.clip(y_interp, 0, 14)
        elif metodo == 'polynomial':
            try:
                k = min(3, len(x_known)-1)
                tck = interpolate.splrep(x_known, y_known, s=0, k=k)
                return interpolate.splev(x_new, tck, der=0)
            except Exception:
                return np.interp(x_new, x_known, y_known)
        else:
            return np.interp(x_new, x_known, y_known)

# ==================== GERENCIADOR DE DADOS ====================
class GerenciadorDados:
    def __init__(self):
        self.lock = threading.Lock()
        self.sensor_data = {}          # sensor_type -> DataFrame
        self.sensor_metadata = {}       # sensor_type -> dict
        self.messages_received = 0
        self.last_message_time = None
        self.novos_dados = False

    def adicionar_ponto(self, sensor_type, timestamp_ms, value, interpolation, metadata):
        try:
            with self.lock:
                # Metadados
                if sensor_type not in self.sensor_metadata:
                    self.sensor_metadata[sensor_type] = {}
                self.sensor_metadata[sensor_type].update(metadata)
                self.sensor_metadata[sensor_type]['interpolation'] = interpolation

                # Dados
                if sensor_type not in self.sensor_data:
                    self.sensor_data[sensor_type] = pd.DataFrame(columns=['timestamp', 'value'])
                new_row = pd.DataFrame({
                    'timestamp': [timestamp_ms],
                    'value': [float(value)]
                })
                self.sensor_data[sensor_type] = pd.concat(
                    [self.sensor_data[sensor_type], new_row], ignore_index=True
                )
                # Limitar tamanho
                if len(self.sensor_data[sensor_type]) > 1000:
                    self.sensor_data[sensor_type] = self.sensor_data[sensor_type].iloc[-1000:]

                self.messages_received += 1
                self.last_message_time = datetime.now()
                self.novos_dados = True
                logger.info(f"✅ Ponto adicionado: {sensor_type} = {value:.3f} em {timestamp_ms}")
        except Exception as e:
            logger.error(f"Erro ao adicionar ponto para {sensor_type}: {e}")

    def obter_dados_brutos(self, sensor_type, horas=24):
        with self.lock:
            df = self.sensor_data.get(sensor_type, pd.DataFrame()).copy()
        if df.empty:
            return pd.DataFrame(columns=['datetime', 'value', 'is_interpolated'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(LOCAL_TIMEZONE)
        cutoff = datetime.now(pytz.UTC) - timedelta(hours=horas)
        cutoff_local = cutoff.astimezone(LOCAL_TIMEZONE)
        df = df[df['datetime'] >= cutoff_local].copy()
        df['is_interpolated'] = False
        return df[['datetime', 'value', 'is_interpolated']]

    def obter_dados_interpolados(self, sensor_type, interval_seconds=60, horas=None):
        with self.lock:
            df = self.sensor_data.get(sensor_type, pd.DataFrame()).copy()
        if df.empty or len(df) < 2:
            return pd.DataFrame(columns=['datetime', 'value', 'is_interpolated'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(LOCAL_TIMEZONE)
        df = df.sort_values('datetime')
        start = df['datetime'].min()
        end = df['datetime'].max()
        regular = pd.date_range(start=start, end=end, freq=f'{interval_seconds}S', tz=LOCAL_TIMEZONE)
        x_known = df['datetime'].astype(np.int64) // 10**6
        y_known = df['value'].values
        x_new = regular.astype(np.int64) // 10**6
        metodo = self.sensor_metadata.get(sensor_type, {}).get('interpolation', 'linear')
        try:
            y_new = InterpoladorSeletivo.interpolar(x_known, y_known, x_new, metodo)
        except Exception as e:
            logger.error(f"Erro na interpolação: {e}")
            y_new = np.interp(x_new, x_known, y_known)
        interp_df = pd.DataFrame({
            'datetime': regular,
            'value': y_new,
            'is_interpolated': True
        }).dropna(subset=['value'])
        
        # Filtrar pelo período, se especificado
        if horas is not None:
            cutoff = datetime.now(pytz.UTC) - timedelta(hours=horas)
            cutoff_local = cutoff.astimezone(LOCAL_TIMEZONE)
            interp_df = interp_df[interp_df['datetime'] >= cutoff_local].copy()
        return interp_df

    def obter_dados_combinados(self, sensor_type, horas=24, interval_seconds=60):
        raw = self.obter_dados_brutos(sensor_type, horas)
        interp = self.obter_dados_interpolados(sensor_type, interval_seconds, horas=horas)
        combined = pd.concat([raw, interp], ignore_index=True)
        return combined.sort_values('datetime', ascending=False)

    def obter_valor_mais_recente(self, sensor_type):
        with self.lock:
            df = self.sensor_data.get(sensor_type, pd.DataFrame())
        if df.empty:
            return None
        return df.sort_values('timestamp')['value'].iloc[-1]

    def tem_dados(self):
        with self.lock:
            return any(len(df) > 0 for df in self.sensor_data.values())

    def tipos_sensor(self):
        with self.lock:
            return list(self.sensor_data.keys())

    def metadados(self, sensor_type):
        return self.sensor_metadata.get(sensor_type, {})

    def ultimo_timestamp_dado(self):
        with self.lock:
            max_ts = None
            for df in self.sensor_data.values():
                if not df.empty:
                    ts = df['timestamp'].max()
                    if max_ts is None or ts > max_ts:
                        max_ts = ts
        if max_ts is not None:
            return pd.to_datetime(max_ts, unit='ms', utc=True).tz_convert(LOCAL_TIMEZONE)
        return None

# ==================== CLIENTE MQTT (CORRIGIDO) ====================
class ClienteMQTT:
    def __init__(self, gerenciador, broker, port):
        self.gerenciador = gerenciador
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(client_id=f"cfe-dash-{int(time.time())}", clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        self.connection_error = None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self.connection_error = None
            logger.info(f"✅ Conectado ao broker {self.broker}:{self.port}")
            client.subscribe(TOPIC_DATA)
        else:
            self.connected = False
            self.connection_error = f"Código {rc}"
            logger.error(f"❌ Falha na conexão MQTT: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            self.connection_error = "Conexão perdida"
            logger.warning(f"Desconectado inesperadamente: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            logger.info(f"Mensagem recebida no tópico {msg.topic}")
            logger.debug(f"Payload: {payload[:200]}...")
            data = json.loads(payload)

            # Extrair timestamp global da mensagem
            ts_str = data.get('transmission_timestamp')
            if ts_str:
                try:
                    # Converte string ISO para datetime e depois para timestamp em ms
                    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S.%f')
                    # Assume que o timestamp está em UTC (ou ajuste conforme necessário)
                    dt_utc = pytz.UTC.localize(dt)
                    timestamp_ms = int(dt_utc.timestamp() * 1000)
                except Exception as e:
                    logger.error(f"Erro ao converter timestamp '{ts_str}': {e}")
                    timestamp_ms = int(time.time() * 1000)  # fallback para agora
            else:
                timestamp_ms = int(time.time() * 1000)
                logger.warning("Mensagem sem transmission_timestamp, usando horário atual")

            if 'readings' in data:
                self._processar_readings(data['readings'], timestamp_ms)
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")

    def _processar_readings(self, readings, timestamp_ms):
        for idx, r in enumerate(readings):
            try:
                sensor_type = r.get('sensor_type')
                value = r.get('value')
                interpolation = r.get('interpolation', 'linear')
                metadata = r.get('metadata', {})
                if sensor_type and value is not None:
                    self.gerenciador.adicionar_ponto(
                        sensor_type, timestamp_ms, value, interpolation, metadata
                    )
                else:
                    logger.warning(f"Leitura {idx} ignorada - campos ausentes: {r}")
            except Exception as e:
                logger.error(f"Erro ao processar leitura {idx}: {e}")

    def conectar(self):
        try:
            logger.info(f"Tentando conectar a {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            time.sleep(2)
            if not self.connected:
                self.connection_error = "Timeout após connect"
        except Exception as e:
            self.connected = False
            self.connection_error = str(e)
            logger.error(f"Exceção na conexão: {e}")

    def desconectar(self):
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False

# ==================== FUNÇÕES AUXILIARES ====================
def testar_broker(broker, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((broker, port))
        sock.close()
        return result == 0
    except:
        return False

def obter_cor(sensor_type):
    import hashlib
    return "#" + hashlib.md5(sensor_type.encode()).hexdigest()[:6]

def criar_grafico(df_raw, df_interp, nome, unidade, cor, faixa=None):
    fig = go.Figure()

    # Adiciona a faixa ótima (apenas visual, não afeta o range do eixo Y)
    if faixa and len(faixa) == 2 and faixa[0] is not None and faixa[1] is not None:
        fig.add_hrect(
            y0=faixa[0], y1=faixa[1],
            line_width=0, fillcolor="lightgreen", opacity=0.2,
            layer='below'  # Garante que fique atrás dos dados
        )

    # Adiciona traces (dados interpolados e brutos)
    if not df_interp.empty:
        fig.add_trace(go.Scatter(
            x=df_interp['datetime'], y=df_interp['value'],
            mode='lines+markers', name='Interpolado',
            line=dict(color=cor, width=2, dash='dash'),
            marker=dict(size=6, color=cor), opacity=0.8
        ))

    if not df_raw.empty:
        fig.add_trace(go.Scatter(
            x=df_raw['datetime'], y=df_raw['value'],
            mode='lines+markers', name='Recebido',
            line=dict(color=cor, width=3),
            marker=dict(size=8, color=cor), opacity=0.9
        ))

    # Ajusta o eixo Y com base apenas nos dados (ignora a faixa ótima)
    if not df_raw.empty or not df_interp.empty:
        # Combina os valores não nulos de ambos os dataframes
        valores = pd.concat([df_raw['value'], df_interp['value']], ignore_index=True).dropna()
        if not valores.empty:
            min_val = valores.min()
            max_val = valores.max()
            # Adiciona uma margem de 5% para melhor visualização
            margin = (max_val - min_val) * 0.05 if max_val != min_val else 0.5
            fig.update_yaxes(range=[min_val - margin, max_val + margin])

    # Layout final
    fig.update_layout(
        title=nome,
        xaxis_title="Tempo",
        yaxis_title=f"{nome} ({unidade})",
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=50, b=30)
    )
    fig.update_traces(line_shape='spline')
    return fig

def tabela_dados(df):
    if df.empty:
        st.info("Sem dados")
        return
    
    df = df.copy()
    df = df.sort_values('datetime', ascending=False).reset_index(drop=True)
    df.insert(0, 'ID', range(len(df), 0, -1))
    df['Data/Hora'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['Valor'] = df['value'].apply(lambda x: f"{x:.3f}")
    df['Tipo'] = df['is_interpolated'].apply(lambda x: 'Interpolado' if x else 'Recebido')
    
    # Seleciona apenas as colunas desejadas para exibição
    df_display = df[['ID', 'Data/Hora', 'Valor', 'Tipo']]

    # Função para colorir a linha inteira com base no valor da coluna 'Tipo'
    def colorir_linha(linha):
        cor = '#E8F5E9' if linha['Tipo'] == 'Recebido' else '#FFF3E0'
        return [f'background-color: {cor}'] * len(linha)

    # Aplica o estilo linha a linha
    styled_df = df_display.style.apply(colorir_linha, axis=1)

    # Exibe a tabela com estilo
    st.dataframe(styled_df, use_container_width=True, height=400)

    # Legenda colorida no rodapé
    st.markdown(
        "📥 <span style='background-color:#E8F5E9; padding:2px 8px; border-radius:4px; font-weight:500;'>Recebido</span> "
        "| 📊 <span style='background-color:#FFF3E0; padding:2px 8px; border-radius:4px; font-weight:500;'>Interpolado</span>",
        unsafe_allow_html=True
    )

def calcular_metricas_interpolacao(sensor_type, horas, interval_seconds, tolerancia_percentual=5):
    """
    Retorna dicionário com métricas de qualidade da interpolação:
    - mae: erro absoluto médio
    - mape: erro percentual absoluto médio
    - acuracia: % de pontos com erro percentual <= tolerancia_percentual
    - total_pontos: número de pontos brutos usados na comparação
    """
    df_raw = st.session_state.gerenciador.obter_dados_brutos(sensor_type, horas)
    df_interp = st.session_state.gerenciador.obter_dados_interpolados(sensor_type, interval_seconds, horas=horas)
    if df_raw.empty or df_interp.empty:
        return None
    # Ordenar e mesclar pelo timestamp mais próximo
    df_raw = df_raw.sort_values('datetime').reset_index(drop=True)
    df_interp = df_interp.sort_values('datetime').reset_index(drop=True)
    merged = pd.merge_asof(df_raw, df_interp, on='datetime', direction='nearest', suffixes=('_raw', '_interp'))
    # Erros
    erro_abs = (merged['value_raw'] - merged['value_interp']).abs()
    erro_percentual = (erro_abs / merged['value_raw'].abs()) * 100
    erro_percentual = erro_percentual.replace([np.inf, -np.inf], np.nan)  # evitar divisão por zero
    # Métricas
    mae = erro_abs.mean()
    mape = erro_percentual.mean(skipna=True)
    acuracia = (erro_percentual <= tolerancia_percentual).mean() * 100 if not erro_percentual.isna().all() else 0
    return {
        'mae': mae,
        'mape': mape,
        'acuracia': acuracia,
        'total_pontos': len(merged)
    }

# ==================== APLICAÇÃO PRINCIPAL ====================
def main():
    st.title("🌱 CFE-HYDRO - Monitoramento")
    # st.markdown("Monitoramento com **interpolação seletiva** – metadados extraídos automaticamente.")
    st.write("Monitoramento com **interpolação seletiva** – metadados extraídos automaticamente.")

    # Estado da sessão
    if 'gerenciador' not in st.session_state:
        st.session_state.gerenciador = GerenciadorDados()
        st.session_state.cliente = None
        st.session_state.broker = DEFAULT_BROKER
        st.session_state.port = DEFAULT_PORT
        st.session_state.ultima_atualizacao = datetime.now()
        st.session_state.intervalo = 30

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        with st.expander("🔧 Broker MQTT", expanded=False):
            broker = st.text_input("Servidor", value=st.session_state.broker)
            port = st.number_input("Porta", min_value=1, max_value=65535, value=st.session_state.port)
            if st.button("Testar conexão"):
                if testar_broker(broker, port):
                    st.success("Broker acessível")
                else:
                    st.error("Não foi possível conectar")
            if st.button("Conectar"):
                if st.session_state.cliente:
                    st.session_state.cliente.desconectar()
                st.session_state.broker = broker
                st.session_state.port = port
                st.session_state.cliente = ClienteMQTT(st.session_state.gerenciador, broker, port)
                st.session_state.cliente.conectar()
                st.rerun()

        st.subheader("📡 Status")
        if st.session_state.cliente and st.session_state.cliente.connected:
            st.success("✅ Conectado")
        else:
            st.error("❌ Desconectado")
            if st.session_state.cliente and st.session_state.cliente.connection_error:
                st.caption(f"Erro: {st.session_state.cliente.connection_error}")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Mensagens", st.session_state.gerenciador.messages_received)
        with col2:
            st.metric("Sensores", len(st.session_state.gerenciador.tipos_sensor()))

        st.subheader("👁️ Visualização")
        
        intervalo = st.slider("Intervalo de atualização (s)", 5, 60, 30)
        st.session_state.intervalo = intervalo

        horas = st.slider("Período visualizado (h)", 1, 72, 1)
        interp_interval = st.slider("Intervalo de Interpolação (s)", 10, 300, 20, step=5)

        if st.button("🧹 Limpar dados"):
            st.session_state.gerenciador = GerenciadorDados()
            st.rerun()

        # st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")
        ultimo_dado = st.session_state.gerenciador.ultimo_timestamp_dado()
        with st.expander("🔍 Detalhes"):
            if ultimo_dado:
                st.write(f"Última atualização: {ultimo_dado.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                st.write("Última atualização: Nenhuma")
            st.write("Métricas:")
            st.write("   * MAE (erro absoluto médio)")
            st.write("   * MAPE (erro percentual médio)")
            st.write("   * Acurácia (percentual de pontos interpolados com erro < 5%)")

    # Configura o auto refresh (em milissegundos) – usa o valor do slider
    st_autorefresh(interval=st.session_state.intervalo * 1000, key="auto-refresh")

    # Se não há cliente, criar um com valores padrão
    if st.session_state.cliente is None:
        st.session_state.cliente = ClienteMQTT(st.session_state.gerenciador, st.session_state.broker, st.session_state.port)
        st.session_state.cliente.conectar()

    # Verificar dados
    if not st.session_state.gerenciador.tem_dados():
        if st.session_state.cliente.connected:
            st.info("📡 Conectado, aguardando dados...")
        else:
            st.warning("⚠️ Não conectado. Configure o broker na barra lateral.")
        with st.expander("🔍 Detalhes"):
            st.write(f"Broker: {st.session_state.broker}:{st.session_state.port}")
            st.write(f"Tópico: {TOPIC_DATA}")
            st.write(f"Mensagens recebidas: {st.session_state.gerenciador.messages_received}")
            st.write(f"Sensores com dados: {st.session_state.gerenciador.tipos_sensor()}")
    else:
        # ========== EXIBIÇÃO DOS DADOS ==========
        sensores = st.session_state.gerenciador.tipos_sensor()
        # st.write("Sensores detectados:", sensores)  # Debug

        # Últimos valores
        st.header("📈 Últimos valores")
        cols = st.columns(min(len(sensores), 4))
        valores_recentes = {}
        for i, sensor in enumerate(sensores[:4]):
            with cols[i]:
                meta = st.session_state.gerenciador.metadados(sensor)
                unit = meta.get('unit', '')
                desc = meta.get('description', sensor)
                opt_min = meta.get('optimal_min')
                opt_max = meta.get('optimal_max')
                valor = st.session_state.gerenciador.obter_valor_mais_recente(sensor)
                valores_recentes[sensor] = valor
                if valor is not None:
                    if opt_min is not None and opt_max is not None:
                        dentro = opt_min <= valor <= opt_max
                        icone = "✅" if dentro else "⚠️"
                        ajuda = f"Ótimo: {opt_min}-{opt_max}{unit}"
                    else:
                        icone = "ℹ️"
                        ajuda = "Faixa não definida"
                    st.metric(label=f"{desc} {icone}", value=f"{valor:.2f}{unit}", help=ajuda)
                else:
                    st.metric(label=desc, value="--")

        # Gráficos em abas
        st.header("📊 Evolução")
        if sensores:
            tabs = st.tabs([s.capitalize() for s in sensores])
            for tab, sensor in zip(tabs, sensores):
                with tab:
                    meta = st.session_state.gerenciador.metadados(sensor)
                    unit = meta.get('unit', '')
                    desc = meta.get('description', sensor)
                    opt_min = meta.get('optimal_min')
                    opt_max = meta.get('optimal_max')
                    faixa = (opt_min, opt_max) if opt_min is not None and opt_max is not None else None
                    cor = obter_cor(sensor)

                    df_raw = st.session_state.gerenciador.obter_dados_brutos(sensor, horas)
                    df_interp = st.session_state.gerenciador.obter_dados_interpolados(sensor, interp_interval, horas=horas)

                    if not df_raw.empty or not df_interp.empty:
                        fig = criar_grafico(df_raw, df_interp, desc, unit, cor, faixa)
                        st.plotly_chart(fig, use_container_width=True)

                        if not df_raw.empty:
                            vals = df_raw['value'].dropna()
                            if len(vals) > 0:
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Média", f"{vals.mean():.2f}{unit}")
                                col2.metric("Mínimo", f"{vals.min():.2f}{unit}")
                                col3.metric("Máximo", f"{vals.max():.2f}{unit}")

                        with st.expander("📋 Ver dados"):
                            df_comb = st.session_state.gerenciador.obter_dados_combinados(sensor, horas, interp_interval)
                            tabela_dados(df_comb)
                    else:
                        st.info("Sem dados no período")

        # Análise qualitativa (agora baseada na precisão da interpolação)
        if sensores:
            st.header("🔍 Qualidade da Interpolação")
            metricas_por_sensor = {}
            for sensor in sensores:
                metricas = calcular_metricas_interpolacao(sensor, horas, interp_interval, tolerancia_percentual=0.05)
                if metricas:
                    metricas_por_sensor[sensor] = metricas

            if metricas_por_sensor:
                num_mostrar = min(len(metricas_por_sensor), 5)
                # Cria colunas: uma para cada sensor + uma extra para a média
                cols = st.columns(num_mostrar + 1)

                for i, (sensor, met) in enumerate(list(metricas_por_sensor.items())[:num_mostrar]):
                    with cols[i]:
                        meta = st.session_state.gerenciador.metadados(sensor)
                        desc = meta.get('description', sensor)
                        st.metric(f"{desc}", f"{met['mae']:.3f}", delta=None)
                        st.caption(f"MAE: {met['mae']:.3f} | MAPE: {met['mape']:.2f}%")
                        st.progress(min(met['acuracia']/100, 1.0))
                        st.caption(f"Acurácia (<5%): {met['acuracia']:.2f}%")

                # Média das métricas na última coluna
                with cols[-1]:
                    mae_medio = np.mean([m['mae'] for m in metricas_por_sensor.values()])
                    acuracia_media = np.mean([m['acuracia'] for m in metricas_por_sensor.values()])
                    st.metric("Média", f"{mae_medio:.3f}", delta=None)
                    st.caption(f"MAE médio: {mae_medio:.3f}%")
                    st.progress(min(acuracia_media/100, 1.0))
                    st.caption(f"Acurácia média: {acuracia_media:.2f}%")
            else:
                st.info("Dados insuficientes para calcular métricas de interpolação (é necessário pelo menos um ponto real e um interpolado).")

if __name__ == "__main__":
    main()




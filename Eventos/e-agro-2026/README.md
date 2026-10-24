# 💧 IrrigaCerta

> **Assistente de irrigação por talhão baseado em satélite, clima e agronomia — para resiliência hídrica no agro.**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.33-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Sentinel-2](https://img.shields.io/badge/Sentinel--2-Copernicus-2E6B3E)](https://www.copernicus.eu/)
[![Hackathon](https://img.shields.io/badge/Hackathon-E--Agro%202026-5C2E91)](https://e-agro.com.br/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Projeto desenvolvido para o **Hackathon E-Agro 2026** (Salvador/BA, 12–14 de novembro de 2026), na temática de **Resiliência Hídrica no Agro**.

---

## 📖 Sumário

- [Sobre o projeto](#-sobre-o-projeto)
- [O problema](#-o-problema)
- [A solução](#-a-solução)
- [Como funciona](#-como-funciona)
- [Arquitetura](#-arquitetura)
- [Funcionalidades](#-funcionalidades)
- [Screenshots](#-screenshots)
- [Stack tecnológico](#-stack-tecnológico)
- [Fontes de dados](#-fontes-de-dados)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Configuração](#-configuração)
- [Metodologia agronômica](#-metodologia-agronômica)
- [Metodologia computacional](#-metodologia-computacional)
- [Limitações conhecidas](#-limitações-conhecidas)
- [Roadmap](#-roadmap)
- [Equipe](#-equipe)
- [Licença](#-licença)
- [Agradecimentos](#-agradecimentos)

---

## 🌱 Sobre o projeto

O **IrrigaCerta** é uma aplicação web que responde a uma pergunta simples e crítica para o produtor rural:

> **"Devo irrigar hoje? Quanto?"**

A resposta combina três camadas de informação abertas e gratuitas:

1. **Satélite Sentinel-2** → índices de vegetação e umidade (NDVI / NDMI) medidos do espaço.
2. **Clima** (NASA POWER + Open-Meteo) → temperatura, chuva histórica e previsão de 7 dias.
3. **Agronomia** → balanço hídrico do solo segundo a metodologia **FAO-56**, com coeficiente de cultura (Kc) por estádio fenológico.

O resultado é uma recomendação em **linguagem leiga**, com lâmina (mm) e tempo de irrigação convertido para o sistema do produtor (gotejamento, aspersão, pivô).

O projeto foi desenhado para funcionar em três modos:

- 🟢 **Online** — busca dados reais ao vivo.
- 💾 **Cache** — dados pré-carregados, ideal para demo.
- 🔌 **Offline (demo mode)** — sem internet, lê apenas o cache local.

---

## ⚠️ O problema

A disponibilidade de água é um fator estratégico para a produção agropecuária brasileira. Eventos climáticos extremos, estiagens prolongadas e o desperdício nos sistemas produtivos tornam necessária a criação de tecnologias acessíveis.

No semiárido brasileiro (Petrolina/PE e Juazeiro/BA, foco do projeto), o produtor irrigante enfrenta três dores recorrentes:

| Dor | Consequência |
|---|---|
| **Quando irrigar?** — decisão "no feeling" | Estresse hídrico e perda de produtividade |
| **Quanto irrigar?** — sem medição de umidade do solo | Desperdício de água e energia elétrica |
| **Onde perde água?** — sem diagnóstico do sistema | Custo operacional maior e menor sustentabilidade |

Soluções existentes no mercado são caras (sensores físicos), proprietárias ou focadas em grandes propriedades. Faltam ferramentas **acessíveis**, **explicáveis** e que usem **dados abertos**.

---

## 💡 A solução

O **IrrigaCerta** entrega **recomendação diária de irrigação por talhão**, sem necessidade de sensores físicos, usando exclusivamente dados abertos:

- **Entrada:** centroide do talhão, cultura, data de plantio, textura do solo, sistema de irrigação e vazão.
- **Processamento:** balanço hídrico diário + índices de satélite + previsão de chuva.
- **Saída:** recomendação clara ("Regue hoje — 12 mm ≈ 2,2 h"), barras de status e gráficos explicativos.

**Diferenciais técnicos:**

- ✅ Sem dependência de hardware instalado no campo.
- ✅ Modelo **explicável** (não é caixa-preta) — o produtor vê o porquê da recomendação.
- ✅ Funciona **offline** após a primeira busca (cache em JSON).
- ✅ Todo o processamento de satélite é feito em **subprocesso isolado** — falhas do GDAL não derrubam a aplicação.
- ✅ Linguagem adaptada ao produtor leigo (não para o técnico).

---

## ⚙️ Como funciona

{GRÁFICO}


---

## 🏗 Arquitetura

O projeto segue uma arquitetura **monolítica em camadas**, com separação clara entre lógica de domínio e apresentação. A escolha por Streamlit (em vez de React + FastAPI) foi deliberada para um hackathon de 3 dias: produtividade de desenvolvimento > separação completa.

{GRÁFICO}



**Decisões arquiteturais notáveis:**

| Decisão | Motivo |
|---|---|
| Satélite em **subprocesso** | Contorna segfault do GDAL no Windows; falha isolada |
| **Cache em JSON** (não em memória) | Demo offline + retomada rápida entre reruns |
| **SQLite** para talhões | Zero setup, arquivo único, fácil de versionar em dev |
| Tiles do satélite passados **no construtor** do `folium.Map` | Evita bug do Leaflet Draw que não finaliza o polígono |
| `draw_options` no `Draw()` | Correção definitiva do mesmo bug (validada na issue #178 do streamlit-folium) |

---

## ✨ Funcionalidades

### Cadastro de talhão
- 🎨 **Desenho no mapa** (polígono/retângulo) com tiles de satélite.
- 📍 **Coordenadas + área** (método 100% confiável, gera quadrado).
- 📁 **Upload de GeoJSON/KML** (Google Earth, QGIS, etc.).
- ✅ Validação de auto-interseção e área.
- ⚠️ Aviso quando o talhão é grande demais (> 500 ha).

### Dashboard
- 💧 **Recomendação em linguagem leiga** com explicação do "porquê".
- 📊 **Barra de progresso** de água no solo (Dr / TAW).
- 🛰️ **Gráfico de NDMI** com faixas seca/moderada/úmida.
- 💧 **Gráfico de balanço hídrico** com zonas segura/alerta.
- 📅 Datas em **português** (`21/out`) sem depender de locale.
- ❓ **Expanders explicativos** — "O que é NDMI?", "O que significa TAW?".

### Gestão
- 🗑️ Excluir talhão + caches associados.
- 🔄 Re-buscar clima / satélite manualmente.
- 🗺️ Seletor de **15 estilos de mapa** (Google, Esri, OSM, CARTO, Sentinel-2).
- 💾 Modo **offline** (`IRRIGACERTA_DEMO_MODE=1`).

---

## 📸 Screenshots

> **Nota:** substitua os placeholders abaixo por imagens reais do app. Sugestão de nomes em cada seção.

### Dashboard principal
![Dashboard do IrrigaCerta mostrando mapa do talhão e recomendação de irrigação](docs/screenshots/dashboard.png)

*Mapa de satélite + recomendação em linguagem leiga + barra de nível de água no solo.*

### Gráfico de balanço hídrico
![Gráfico Plotly do balanço hídrico com zonas segura e de alerta](docs/screenshots/balanco_hidrico.png)

*Linha de consumo de água, com faixas coloridas mostrando zona segura (verde) e de alerta (vermelho).*

### Gráfico de umidade via satélite (NDMI)
![Gráfico Plotly do NDMI mostrando tendência de seca ao longo do tempo](docs/screenshots/ndmi.png)

*Tendência de umidade das plantas vista do espaço (Sentinel-2).*

### Cadastro por desenho
![Tela de cadastro com mapa de satélite e ferramenta de desenho de polígono](docs/screenshots/cadastro.png)

*Polígono desenhado sobre lavoura real.*

---

## 🛠 Stack tecnológico

| Camada | Tecnologia | Versão | Por quê |
|---|---|---|---|
| **App** | Streamlit | 1.33.0 | Prototipagem rápida, estado de sessão |
| **Mapas** | Folium + streamlit-folium | 0.16 / 0.20 | Leaflet robusto, tiles abertos |
| **Gráficos** | Plotly | ≥ 5.20 | Responsivo, interativo, PT-BR sem locale |
| **Raster** | rasterio | ≥ 1.3 | Leitura de COG (Sentinel-2) |
| **Geometria** | Shapely + pyproj | ≥ 2.0 / 3.6 | Validação e projeção |
| **Dados** | pandas + numpy | ≥ 2.2 / 1.26 | Séries e agregação |
| **Persistência** | SQLite | (nativo) | Zero setup |
| **Config** | python-dotenv | ≥ 1.0 | `.env` versionável |

> **Versões pinadas** (`streamlit==1.33.0`, `streamlit-folium==0.20.0`, `folium==0.16.0`) são necessárias para o correto funcionamento do Leaflet Draw no cadastro. Ver [Limitações conhecidas](#-limitações-conhecidas).

---

## 🛰 Fontes de dados

| Fonte | O que fornece | Acesso | Custo | Referência |
|---|---|---|---|---|
| **Sentinel-2 L2A** | NDVI, NDMI (bandas B04, B08, B11, SCL) | [Earth Search (STAC)](https://earth-search.aws.element84.com/v1) | Gratuito, sem chave | [Copernicus](https://www.copernicus.eu/) |
| **NASA POWER** | Tmax, Tmin, chuva, umidade, vento, radiação | [power.larc.nasa.gov](https://power.larc.nasa.gov/) | Gratuito, sem chave | [NASA LaRC](https://power.larc.nasa.gov/) |
| **Open-Meteo** | Previsão de chuva e temperatura (7 dias) | [open-meteo.com](https://open-meteo.com/) | Gratuito, sem chave | [Open-Meteo](https://open-meteo.com/) |
| **Tiles de mapa** | Satélite, híbrido, ruas, topográfico | Google / Esri / OSM / CARTO / EOX | Gratuito (ver licenças) | Ver `TILE_PROVIDERS` no `app.py` |

### Fórmulas

**NDVI** (Normalized Difference Vegetation Index) — vigor da vegetação:

{GRÁFICOS}

## 🚀 Instalação

### Pré-requisitos

- **Python 3.11+** (testado em 3.12)
- **pip** + **venv**
- Internet (para primeira busca); não é necessário após o cache.

### Passo a passo

# 1. Clone o repositório
git clone https://github.com/<seu-usuario>/irrigacerta.git
cd irrigacerta

# 2. Crie e ative o ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env conforme necessário (ver seção Configuração)

# 5. (Opcional) Aqueça o cache para demo offline
python -m scripts.prefetch_demo

# 6. Suba o app
streamlit run app.py

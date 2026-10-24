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

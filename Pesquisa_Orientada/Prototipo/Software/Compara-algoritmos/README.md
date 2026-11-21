# 🔬 Otimizador de Rota XY — Scanner histológico de baixo custo

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://SEU-USUARIO-otimizador-rota-xy.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Aplicação **Streamlit** que compara **8 algoritmos** de ordenação de visitas
em uma bandeja de lâminas histológicas (8 colunas × 2 linhas = 16 posições),
com o objetivo de **minimizar a distância total percorrida** por um atuador
XY de baixo custo. Para cada algoritmo, o app mede:

- **Distância total (mm)** — caminho percorrido desde a origem até a última lâmina
- **Tempo de cálculo (s)** — custo computacional da decisão
- **Gap %** — diferença percentual em relação à melhor rota encontrada
- **Animação passo a passo** — visualização do deslocamento sobre a bandeja

Algoritmos implementados:

| # | Algoritmo | Tipo |
|---|---|---|
| 1 | Ordem Original | baseline (linha a linha) |
| 2 | Vizinho Mais Próximo (NN) | heurística gulosa |
| 3 | Inserção Mais Próxima (NI) | heurística construtiva |
| 4 | 2-opt sobre NN | melhoria local |
| 5 | 2-opt sobre Inserção | melhoria local |
| 6 | Algoritmo Genético (OX) | metaheurística evolutiva |
| 7 | Simulated Annealing | metaheurística estocástica |
| 8 | Força Bruta | exato (até 10 lâminas) |

---

## 📑 Índice

- [Demonstração online](#-demonstração-online)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Contexto físico: a bandeja e o atuador XY](#-contexto-físico-a-bandeja-e-o-atuador-xy)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Detalhes dos algoritmos](#-detalhes-dos-algoritmos)
- [Métricas da bandeja](#-métricas-da-bandeja)
- [Deploy no Streamlit Cloud](#-deploy-no-streamlit-cloud)
- [Limitações conhecidas](#-limitações-conhecidas)
- [Referências](#-referências)
- [Licença](#-licença)

---

## 🚀 Demonstração online

🔗 **[Abrir no Streamlit Cloud](https://SEU-USUARIO-otimizador-rota-xy.streamlit.app)**

A versão online é **totalmente funcional** — este app é puro cálculo +
visualização, sem dependência de hardware. Isso o torna ideal para:

- Compartilhar o link com orientador/banca durante a defesa
- Ilustrar o método em artigo/tese com resultados reprodutíveis
- Servir de material didático em disciplinas de otimização combinatória
- Comparar algoritmos sem precisar de um scanner físico

---

## 📁 Estrutura do repositório

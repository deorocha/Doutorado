# 🏷️ Gerador de Etiquetas QR para Lâminas Histológicas

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://SEU-USUARIO-etiquetas-laminas.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Aplicação **Streamlit** que gera **folhas A4 de etiquetas adesivas com
QR-code**, prontas para identificar lâminas histológicas em laboratórios
de anatomia patológica. A partir de um intervalo numérico e um prefixo, o
app produz um **PDF com uma folha por grupo de etiquetas**, cada etiqueta
contendo:

- **Identificador legível** (ex.: `L-01.05.001`) em Helvetica-Bold 8 pt
- **Data e hora de geração** em Helvetica 7 pt
- **QR-code** (13 × 13 mm) codificando o identificador

O PDF é gerado com **posicionamento em milímetros** (ReportLab +
`lib.units.mm`), com QR desenhado nativamente como vetor (sem dependência
de `qrcode`/`Pillow`). A interface oferece **preview inline**, **download**
e um **botão de impressão** que abre o PDF em nova aba.

---

## ⚠️ Nota importante: o nome "Pimaco A4248" e o que o código gera

O título do app e o nome do arquivo PDF dizem **"Pimaco A4248"**, mas os
**parâmetros de layout no `app.py` não correspondem ao gabarito A4248**:

| Parâmetro | Código atual (`app.py`) | Pimaco A4248 oficial |
|---|---|---|
| Etiquetas por folha | **96** (6 × 16) | **8** (2 × 4) |
| Tamanho da etiqueta | **31 × 17 mm** | 99,1 × 67,7 mm |
| Formato | mini-etiqueta | etiqueta grande (endereço) |
| Uso típico | microtubos, lâminas, tubos | caixas, envelopes |

Ou seja, o código implementa um **gabarito de mini-etiquetas (96/página)**
e não o A4248. Isso não é necessariamente um erro — 96 mini-etiquetas de
31 × 17 mm **funcionam muito bem para identificar lâminas** (o topo fosco
da lâmina tem cerca de 20–25 mm de largura útil). Mas o PDF gerado **não
vai encaixar** em uma folha física A4248; vai encaixar em uma folha de
mini-etiquetas equivalente ao gabarito codificado.

**Duas opções:**

1. **Manter como está** e renomear para "Mini-etiquetas A4 (96/página)".
   Funciona para lâminas; é mais barato por etiqueta; rende 96 IDs/folha.
2. **Trocar as constantes** para A4248 real (ver
   [Como ajustar para A4248 real](#-como-ajustar-para-a4248-real)).

Ambas são válidas. O importante é **medir a folha física** antes de
imprimir em lote — ±0,5 mm desalinha.

---

## 📑 Índice

- [Demonstração online](#-demonstração-online)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [O que o app gera](#-o-que-o-app-gera)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Como ajustar para A4248 real](#-como-ajustar-para-a4248-real)
- [Detalhes técnicos](#-detalhes-técnicos)
- [Deploy no Streamlit Cloud](#-deploy-no-streamlit-cloud)
- [Limitações conhecidas](#-limitações-conhecidas)
- [Boas práticas LGPD](#-boas-práticas-lgpd)
- [Referências](#-referências)
- [Licença](#-licença)

---

## 🚀 Demonstração online

🔗 **[Abrir no Streamlit Cloud](https://SEU-USUARIO-etiquetas-laminas.streamlit.app)**

O app **não depende de hardware**, então roda 100% na nuvem. Todas as
funcionalidades funcionam online:

- Geração do PDF com N etiquetas
- Preview inline via `streamlit-pdf-viewer`
- Download do PDF
- Botão de impressão (abre o PDF em nova aba e chama `print()`)

A única coisa que **não** acontece no Cloud é a impressão em si — o
servidor não tem acesso à sua impressora. Mas isso é irrelevante na
prática: você **gera** o PDF no Cloud, **baixa** e **imprime** localmente.

---

## 📁 Estrutura do repositório

```
Etiquetas-Laminas-QR/
│
├── app.py                          # Aplicação Streamlit (ponto de entrada)
├── requirements.txt                # Dependências (Streamlit + ReportLab + PDF viewer)
├── README.md                       # Este arquivo
├── LICENSE                         # Licença MIT
├── .gitignore                      # Arquivos que não devem ir ao Git
│
├── .streamlit/
│   └── config.toml                 # Tema, telemetria desligada
│
└── docs/
    ├── screenshot-form.png         # Captura da sidebar
    ├── screenshot-preview.png      # Captura do preview inline
    └── etiquetas-impressas.jpg     # Foto das etiquetas na lâmina (opcional)
```

### Descrição de cada arquivo

| Arquivo | Conteúdo |
|---|---|
| **`app.py`** | Aplicação inteira em um único arquivo: geração do QR nativo (ReportLab), montagem do PDF em A4, preview inline via `streamlit-pdf-viewer`, sidebar com formulário (inicial/final/prefixo/dígitos). ~120 linhas. |
| **`requirements.txt`** | Dependências (Streamlit, ReportLab, streamlit-pdf-viewer). |
| **`README.md`** | Documentação (este arquivo). |
| **`LICENSE`** | Licença MIT. |
| **`.gitignore`** | Ignora `__pycache__/`, `.venv/`, `*.pdf`, `.streamlit/secrets.toml`. |
| **`.streamlit/config.toml`** | Tema claro, telemetria desligada. |
| **`docs/`** | Imagens para o README. Substitua pelas figuras do seu artigo. |

### O que **não** vai no repositório

Gerados em tempo de execução (já no `.gitignore`):

```
etiquetas_*.pdf
preview_*.png
__pycache__/
.venv/, venv/
.streamlit/secrets.toml
```

---

## 📐 O que o app gera

### Layout atual (96 mini-etiquetas por folha)

O `app.py` posiciona **6 colunas × 16 linhas = 96 etiquetas** de
**31 × 17 mm** cada, com **2 mm de espaço entre colunas** e **0 mm entre
linhas**, **centralizadas** na folha A4:

```
Folha A4 (210 × 297 mm)

┌───────────────────────────────────────────────────┐
│  ← 7 mm                                          │
│  ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐      │
│  │ L-01││ L-01││ L-01││ L-01││ L-01││ L-01│ ...  │
│  │  05.││  05.││  05.││  05.││  05.││  05.│      │  ↑
│  │ 001 ││ 002 ││ 003 ││ 004 ││ 005 ││ 006 │      │  12,5 mm
│  └─────┘└─────┘└─────┘└─────┘└─────┘└─────┘      │  (centro)
│   ...      16 linhas × 17 mm                       │
│  ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐      │  ↓
│  │ 091 ││ 092 ││ 093 ││ 094 ││ 095 ││ 096 │      │
│  └─────┘└─────┘└─────┘└─────┘└─────┘└─────┘      │
│                                          ↓ 12,5 mm│
└───────────────────────────────────────────────────┘
```

- Largura total: 6 × 31 mm + 5 × 2 mm = **196 mm** (margem lateral: 7 mm)
- Altura total: 16 × 17 mm + 15 × 0 mm = **272 mm** (margem sup/inf: 12,5 mm)
- Layout **centralizado**: `margin = (A4 - total) / 2`

### Conteúdo de cada etiqueta (31 × 17 mm)

```
┌───────────────────────────────┐
│ ┌────────┐                    │
│ │        │  L-01.05.001        │  ← ID em Helvetica-Bold 8 pt
│ │  QR    │  21/11/2026         │  ← data em Helvetica 7 pt
│ │ 13 mm  │  14:32:07           │  ← hora em Helvetica 7 pt
│ └────────┘                    │
│                               │
└───────────────────────────────┘
```

- QR tem **13 × 13 mm** e fica alinhado à esquerda (margem 1 mm)
- Texto ocupa o restante à direita, **centralizado horizontalmente**
- **Data e hora** são capturadas em `datetime.now()` no momento da
  geração (portanto **iguais em todas as etiquetas do lote**)

### Paginação

Se você gerar mais de 96 números, cada grupo de 96 vira uma página do
PDF. Ex.: 250 números → **3 folhas** (96 + 96 + 58).

### Impressão

1. Salve o PDF
2. Abra no visualizador do sistema
3. **Escala 100%** (sem "ajustar à página")
4. Imprima na folha adesiva correspondente ao gabarito (96 mini-etiquetas)
5. **Verifique o encaixe antes de imprimir em lote** — pequenas variações
   de lote (±0,5 mm) e o alinhamento da impressora são as causas mais
   comuns de "a etiqueta sai 1 mm deslocada"

---

## ⚙️ Instalação

### Requisitos

- Python **3.10+**
- Windows 10/11, Linux ou macOS
- Impressora **laser ou jato de tinta** (térmica direta não funciona com
  folhas adesivas A4 comuns)
- Navegador moderno (o preview usa `pdf.js` via WASM)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/SEU-USUARIO/etiquetas-laminas-qr.git
cd etiquetas-laminas-qr

# 2. Ambiente virtual (recomendado)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Rode o app
streamlit run app.py
```

O navegador abre automaticamente em `http://localhost:8501`.

### Notas por sistema operacional

**Windows**
- Nenhuma configuração especial. ReportLab e Pillow são wheels nativas.
- Desligue **"Ajustar à página"** no diálogo de impressão (o PDF já está
  em A4 com margens corretas).

**Linux**
- Nenhuma configuração especial. Se faltar `libgl` no servidor, **não é
  problema deste app** — não há OpenCV.
- Use **Evince** ou **Okular** para imprimir, com escala 100%.

**macOS**
- Use **Pré-Visualização** com escala 100%. Não use "Imprimir em escala
  para caber".

---

## 🎮 Uso

### Fluxo básico

1. **Sidebar → Número inicial** — primeiro número da sequência (padrão: 1)
2. **Sidebar → Número final** — último número da sequência (padrão: 50)
3. **Sidebar → Prefixo** — texto fixo antes do número (padrão: `L-01.05.`)
4. **Sidebar → Quantidade de dígitos** — zero-padding do número (padrão: 3)
5. Clique em **Gerar**

O app:

- Valida que `inicial ≤ final` (senão mostra erro)
- Gera a lista `["L-01.05.001", "L-01.05.002", ..., "L-01.05.050"]`
- Cria o PDF em memória com **uma folha por grupo de 96 etiquetas**
- Exibe o PDF inline com `pdf_viewer`
- Disponibiliza **Salvar PDF** (download) e **Imprimir PDF** (abre em nova aba)

### Exemplo de saída

Com `inicial=1`, `final=50`, `prefixo="L-01.05."`, `digitos=3`:

- 50 etiquetas geradas
- **1 folha** (as 50 cabem em uma página de 96 posições)
- IDs: `L-01.05.001` a `L-01.05.050`
- Arquivo: `etiquetas_pimaco_a4248.pdf`

Com `inicial=100`, `final=350`, `prefixo="C-2026-"`, `digitos=4`:

- 251 etiquetas
- **3 folhas** (96 + 96 + 59)
- IDs: `C-2026-0100` a `C-2026-0350`

### O botão "Imprimir PDF"

Ele abre o PDF em uma **nova aba** via `data:application/pdf;base64,...`
e chama `window.print()` no `onload`. Funciona bem no desktop, mas tem
**três limitações** (detalhadas em
[Limitações conhecidas](#-limitações-conhecidas)):

1. **Bloqueio de pop-up** — o navegador pode bloquear a nova aba
2. **Timing** — em alguns visualizadores, `onload` dispara **antes** do
   PDF terminar de carregar, então o `print()` abre uma página em branco
3. **Tamanho do data URI** — PDFs muito grandes (>2 MB) podem falhar
   silenciosamente (Chrome limita data URIs a ~2 MB)

**Fallback robusto**: use o botão **💾 Salvar PDF** e imprima pelo
visualizador do sistema. Sempre funciona.

### Dica: "modo artigo"

Para a figura do método no artigo:

1. Use uma sequência pequena (ex.: 8–12 etiquetas) para caber no frame
2. Gere o PDF, tire um screenshot do preview inline em zoom 200%
3. Legenda sugerida: *"Layout das etiquetas geradas pelo sistema; QR
   codifica o identificador pseudonimizado da lâmina."*

---

## 🎯 Como ajustar para A4248 real

Se você **quer** de fato o gabarito A4248 (8 etiquetas grandes por folha,
99,1 × 67,7 mm), troque as constantes em `gerar_pdf()`:

```python
# Dentro de gerar_pdf(rotulos):

cols = 2
rows = 4
label_width  = 99.1 * mm
label_height = 67.7 * mm
qr_size      = 30  * mm   # maior, já que sobra espaço

gap_col = 2.5 * mm
gap_row = 0   * mm

# O layout atual centraliza; para A4248 use margens explícitas:
margin_left = 4.7  * mm
margin_top  = 12.5 * mm

# Opcional: substitua o cálculo centrado por:
# margin_left = 4.7 * mm
# margin_top  = 12.5 * mm
# (remova as linhas "margin_left = (page_width - total_width) / 2" etc.)
```

Com essas constantes:

- Largura: 2 × 99,1 + 2,5 = 200,7 mm (sobra 9,3 mm → 4,7 mm cada lado, igual ao oficial)
- Altura: 4 × 67,7 + 0 = 270,8 mm (sobra 26,2 mm → 13,1 mm cada lado, ~0,6 mm acima do oficial)
- **8 etiquetas por folha** — 50 números viram **7 folhas**

O QR de 30 mm cabe folgado em 99 × 67 mm. Os textos (8 pt bold + 7 pt)
também vão parecer minúsculos em uma etiqueta grande — considere subir
para 14 pt e 10 pt:

```python
c.setFont("Helvetica-Bold", 14)
...
c.setFont("Helvetica", 10)
```

### Outros gabaritos

Se você tiver folhas diferentes no laboratório, o processo é o mesmo:
meça a folha física, coloque `cols`, `rows`, `label_width`, `label_height`,
`gap_col`, `gap_row` e as margens corretas. **Sempre teste com uma folha
de rascunho antes de imprimir em lote.**

---

## 🧠 Detalhes técnicos

### Geração do QR: `reportlab.graphics.barcode.qr`

O QR é gerado **nativamente pelo ReportLab**, sem depender da biblioteca
`qrcode` do PyPI. Vantagens:

- **Uma dependência a menos** (sem `qrcode` nem `Pillow` extra)
- **Vetorial**: o QR no PDF é composto de retângulos, então amplia sem
  pixelar e imprime nítido em qualquer DPI
- **Sem passagem por PNG** (`BytesIO` + `drawImage` é desnecessário)

Desvantagem: o ReportLab usa **seus próprios defaults** de correção de
erro (nível M, ~15% de tolerância) e **não expõe API** para mudar para Q
(25%) ou H (30%) sem hackear. Se você precisa de QR mais robusto (ex.:
lâminas que vão para ambiente úmido de coloração), considere trocar por
`qrcode[pil]` + `drawImage` — mas saiba que isso **quebra a vetorização**.

### Escala do QR

O `QrCodeWidget` retorna um `bounds` que depende da **quantidade de
módulos** (proporcional ao número de caracteres codificados). O código
calcula `scale = min(qr_size / qr_width, qr_size / qr_height)` e aplica
`drawing.scale(scale, scale)`. Resultado prático:

- IDs curtos (`L-01.05.001`, 11 chars) → QR com módulos grandes, fácil de ler
- IDs longos (URLs, JSONs, >100 chars) → módulos pequenos, **pode ficar
  ilegível em 13 mm**

Para 13 mm de QR, **mantenha o conteúdo abaixo de ~50 caracteres**. Acima
disso, aumente `qr_size` ou use identificadores mais curtos.

### Timestamp

`data_atual` e `hora_atual` são calculadas **uma vez**, no início de
`gerar_pdf()`, com `datetime.now()`. Todas as etiquetas do lote mostram
a **mesma data/hora** — a da geração do PDF, não a da impressão nem a do
uso da lâmina.

Se você quer que cada etiqueta tenha sua própria data (ex.: data de
processamento do espécime), será preciso passar essa informação por
etiqueta — o formulário atual só permite um prefixo + sequência numérica.

### Layout centralizado vs. margens fixas

O código atual calcula:

```python
margin_left = (page_width  - total_width)  / 2
margin_top  = (page_height - total_height) / 2
```

Isso funciona bem para **mini-etiquetas** onde o gabarito é aproximadamente
simétrico na folha. Para **gabaritos Pimaco oficiais**, as margens são
**fixas e assimétricas** (ex.: A4248 tem 4,7 mm à esquerda e 12,5 mm no
topo). O layout centrado fica ~0,6 mm deslocado do oficial — o que é
tolerável para rascunho, mas não para produção. Se você está migrando
para um gabarito oficial, **substitua o cálculo centrado por margens
fixas**.

### Dependências ausentes que você **não** vai sentir falta

- **`qrcode`** — substituído pelo `reportlab.graphics.barcode.qr`
- **`Pillow`** — não é necessário, o QR é vetorial
- **`pandas`** — a entrada é numérica (inicial/final), não planilha
- **`opencv`**, **`pyserial`**, **`requests`** — o app não acessa hardware
- **`pdf2image`/`poppler`** — o preview usa `streamlit-pdf-viewer` (WASM)

---

## ☁️ Deploy no Streamlit Cloud

### Subir para o GitHub

```bash
cd "caminho/para/etiquetas-laminas-qr"

git init
git add app.py requirements.txt README.md .gitignore .streamlit/config.toml docs/
git commit -m "Gerador de etiquetas QR para lâminas histológicas"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/etiquetas-laminas-qr.git
git push -u origin main
```

### Conectar ao Streamlit Cloud

1. Acesse **https://share.streamlit.io**
2. **Sign in with GitHub** → autorize o acesso ao repositório
3. **New app** → preencha:
   - **Repository**: `SEU-USUARIO/etiquetas-laminas-qr`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **Deploy!** (primeira vez leva ~40 s)

### O que funciona na nuvem

| Recurso | Cloud | Local |
|---|---|---|
| Formulário (inicial/final/prefixo/dígitos) | ✅ | ✅ |
| Geração do PDF (ReportLab) | ✅ | ✅ |
| Preview inline (`streamlit-pdf-viewer`) | ✅ | ✅ |
| Download do PDF | ✅ | ✅ |
| Botão de impressão | ✅ (abre nova aba) | ✅ |
| Impressão física | ❌ (sem impressora no server) | ✅ |

**Conclusão prática:** o Cloud serve para **gerar o PDF**; a impressão é
sempre local (baixe → abra → imprima). Isso é perfeitamente aceitável e
é o fluxo normal de qualquer gerador de etiquetas.

### Atualização automática

Cada `git push` na branch `main` redeploya automaticamente em ~30 s.

---

## ⚠️ Limitações conhecidas

### Do botão "Imprimir PDF"

1. **Bloqueio de pop-up** — o navegador pode bloquear a nova aba; o
   usuário precisa autorizar pop-ups para o site do Streamlit Cloud.
2. **Timing do `onload`** — em alguns navegadores, o `onload` dispara
   **antes** de o visualizador de PDF terminar de renderizar; o `print()`
   abre uma página em branco. Alternativa robusta: baixar e imprimir
   pelo visualizador.
3. **Tamanho do data URI** — Chrome limita `data:` URIs a ~2 MB. Para
   lotes grandes (>~5000 IDs), o botão falha silenciosamente. O botão
   **Salvar PDF** (que usa `st.download_button` com bytes reais) **não
   tem esse limite**.

**Recomendação prática:** prefira **Salvar PDF** e imprima pelo sistema.
O botão de impressão é conveniência, não confiabilidade.

### Do layout

- **Constantes hard-coded** — `cols`, `rows`, `label_width`, etc. estão
  dentro de `gerar_pdf()`. Para variar de formato, edite-as e reinicie.
- **Um gabarito por PDF** — se você tem lotes A4248 e mini-etiquetas,
  gere dois PDFs separados.
- **Centralização** — o layout centrado assume simetria; gabaritos
  oficiais Pimaco têm margens assimétricas. Ver
  [Como ajustar para A4248 real](#-como-ajustar-para-a4248-real).
- **Data/hora fixas por lote** — todas as etiquetas mostram o timestamp
  da geração do PDF, não da impressão ou do uso.

### Do QR

- **Correção de erro não configurável** — ReportLab usa nível M (~15%
  de tolerância). Para ambiente úmido, considere trocar para `qrcode`
  (com `error_correction=ERROR_CORRECT_Q`) — perde-se a vetorização.
- **Conteúdo longo fica ilegível em 13 mm** — acima de ~50 caracteres,
  os módulos ficam pequenos demais. **IDs curtos são obrigatórios**;
  URLs/JSONs longos exigem aumentar `qr_size`.
- **Sem validação de leitura** — o app confia que o `QrCodeWidget` do
  ReportLab gera algo válido. Para robustez, adicione validação com
  `pyzbar` **somente no teste local** (adiciona dependência nativa).

### Do escopo

- **Sem planilha editável** — entrada é apenas intervalo + prefixo +
  zero-padding. Para metadados por lâmina (espécime, data de coleta,
  número de caso), será preciso evoluir o formulário ou ler CSV.
- **Sem logo** — o app atual não imprime logo de laboratório. Fácil de
  adicionar (`c.drawImage` no canto da etiqueta), mas não está no código.
- **Sem integração com LIMS** — não consulta sistema, não valida unicidade
  de IDs entre lotes, não gera log de emissão.
- **Sem código de barras linear** — só QR. Se o laboratório usar leitores
  de Code128, é preciso adicionar (`reportlab.graphics.barcode.code128`).

### Do Streamlit

- **`use_container_width=True`** em `st.download_button` — deprecated a
  partir de 1.40+. O pin `<1.42` mantém funcionando com warning. Para
  migrar, troque por `width="stretch"` (Streamlit ≥1.42).

---

## 🔒 Boas práticas LGPD

As lâminas contêm **dados de saúde** e, mesmo pseudonimizadas, estão no
escopo da **LGPD (Lei 13.709/2018)**.

### O que **pode** ir na etiqueta / no QR

- ✅ Identificador pseudonimizado (`L-01.05.001`, `C-2026-0100`)
- ✅ Data de geração/processamento
- ✅ Prefixo do laboratório
- ✅ Sequência numérica

### O que **não** pode ir

- ❌ Nome do paciente
- ❌ CPF, RG, CNS
- ❌ Data de nascimento
- ❌ Nome do médico solicitante
- ❌ Diagnóstico (mesmo abreviado)

O vínculo entre `L-01.05.001` e o paciente **fica no LIMS**, não na
etiqueta nem no QR. A etiqueta é o ponto de junção criptográfico, não a
fonte.

### Se o QR codificar URL

Use **HTTPS** obrigatoriamente, e o endpoint deve exigir autenticação.
**Não** embuta token de sessão no QR — ele fica impresso e legível por
qualquer um com a lâmina na mão.

### Log de emissão

Para conformidade, guarde (fora do repositório, em `results/` ou similar)
um registro de: quem gerou (operador), quando, qual faixa, para qual
lote de espécimes. O app atual **não** gera esse log — fica como
trabalho futuro ou script separado.

---

## 📚 Referências

Normas e padrões:

- **ISO 8037-1:2021** — *Microscopes — Slides — Part 1: Dimensions and
  optical properties*. Lâminas 26 × 76 mm (ISO 8037).
- **ISO/IEC 18004:2015** — *QR Code bar code symbology specification*.
- **Pimaco — Catálogo A4**. Especificações da linha A4248 (8 etiquetas
  de 99,1 × 67,7 mm) e das mini-etiquetas.

Patologia digital e rastreabilidade:

- **Bian, Z., et al. (2020).** Autofocusing technologies for whole slide
  imaging. *Journal of Pathology Informatics*.
- **OpenWSI** — referência open-source de scanner histológico de baixo
  custo: https://github.com/AndyFooGuo/OpenWSI
- **Brasil. Lei nº 13.709/2018** — Lei Geral de Proteção de Dados
  Pessoais (LGPD).

Bibliotecas usadas:

- **ReportLab User Guide** — https://www.reportlab.com/docs/reportlab-userguide.pdf
  (seções de `QrCodeWidget`, `Drawing`, `canvas.drawImage`, `mm`)
- **Streamlit** — https://docs.streamlit.io
- **streamlit-pdf-viewer** — https://github.com/lfoppiano/streamlit-pdf-viewer

> ⚠️ Verifique cada referência nas bases primárias antes de citar.
> O gabarito Pimaco A4248 pode variar entre lotes; **meça a folha física**
> antes de imprimir em lote.

---

## 🤝 Contribuindo

Sugestões de evolução:

- **Suporte a múltiplos gabaritos** com escolha pela sidebar (A4248,
  mini-etiquetas, Pimaco 6180/6184, etc.)
- **Logo do laboratório** no rodapé de cada etiqueta (via `st.file_uploader`
  + `c.drawImage`)
- **Metadados por lâmina** (espécime, número de caso) via
  `st.data_editor` + pandas
- **Validação de QR** com `pyzbar` no preview (opt-in)
- **Exportação CSV** do lote gerado, para rastreabilidade
- **Trocar botão de impressão por `webbrowser.open`** com fallback
  documentado

## 📄 Licença

Distribuído sob a **licença MIT**. Veja [LICENSE](LICENSE) para o texto
completo. Uso acadêmico e comercial permitido, com atribuição.

## 👤 Autor

**André Rocha**
Doutorando em Ciência da Computação — PGCOMP/UFBA
📧 rocha.a@ufba.br

## 🙏 Agradecimentos

- Meu orientador de Doutorado, Prof. Dr. Luciano Oliveira
- Equipe do Laboratório de Patologia (pela validação do layout em bancada)
- Comunidade open-source do Streamlit e ReportLab
- [OpenFlexure](https://openflexure.org/) e [OpenWSI](https://github.com/AndyFooGuo/OpenWSI)
  — referências de hardware aberto para patologia digital

---
p align="center">
  Feito com 🏷️ e 🔬 para patologia digital acessível
</p>

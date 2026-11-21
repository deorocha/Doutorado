# 🧪 Monitor de Bandejas — Sensores Hall + PCF8574 via Serial

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Local only](https://img.shields.io/badge/deploy-LOCAL%20ONLY-red.svg)](#-por-que-não-funciona-no-cloud)

Aplicação **Streamlit** que monitora em **tempo real** a presença/ausência
das **8 bandejas de lâminas histológicas** de um scanner, lendo **8
sensores Hall 3144** multiplexados por um **PCF8574** (I²C), via porta
serial USB de um Arduino Nano.

- **Painel visual em escala**: cada bandeja é uma barra horizontal
  proporcional a **184 × 8 mm**, com gap de **10 mm** entre bandejas
- **Atualização automática** a cada 300 ms (`streamlit-autorefresh`)
- **Diagnóstico embutido**: bytes recebidos, ciclos completos, última
  linha crua, tabela por slot
- **Thread de leitura** separada (não bloqueia a UI do Streamlit)

---

## ⚠️ Por que não funciona no Cloud

**Este app é *local-only*.** Ele depende de acesso direto à **porta serial
USB** do Arduino Nano — algo que o servidor do Streamlit Cloud **não tem**.

### O que acontece se você deployar no Cloud

1. O app **abre normalmente** (interface, sidebar, legenda, painel vazio)
2. `serial.tools.list_ports.comports()` retorna `[]` → a sidebar mostra
   um `text_input` com valor padrão `/dev/ttyUSB0`
3. Você clica em **▶ Iniciar**
4. A thread tenta abrir `/dev/ttyUSB0` **5 vezes** (com 0,6 s entre tentativas)
5. Após ~3 s, mostra o erro:

   > ❌ Não foi possível abrir **/dev/ttyUSB0** após 5 tentativas.
   > **Último erro:** `[Errno 2] could not open port /dev/ttyUSB0: ...`

6. O app **não trava** — continua na tela, permite editar parâmetros e
   reiniciar. Mas **nunca lerá dados**.

### Conclusão prática

| Uso | Onde rodar |
|---|---|
| **Monitorar o scanner de verdade** | **Local** (seu PC, com o Arduino plugado) |
| Demonstrar a interface para a banca | Cloud (mas avise que não há hardware) |
| Servir de figura no artigo | Local (screenshot do painel com sensores ativos) |

**Este app é parte do "execution layer" do scanner** — ele fala com o
hardware, não faz planejamento offline. Diferente dos apps de planejamento
(otimizador de rota, gerador de etiquetas), **ele precisa de hardware
físico**.

---

## 📑 Índice

- [Demonstração online (limitada)](#-demonstração-online-limitada)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Hardware](#-hardware)
- [Protocolo serial](#-protocolo-serial)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Troubleshooting](#-troubleshooting)
- [Notas de arquitetura](#-notas-de-arquitetura)
- [Limitações conhecidas](#-limitações-conhecidas)
- [Referências](#-referências)
- [Licença](#-licença)

---

## 🚀 Demonstração online (limitada)

🔗 **[Abrir no Streamlit Cloud](https://SEU-USUARIO-monitor-bandejas.streamlit.app)**

> ⚠️ **Na nuvem, apenas a *interface* funciona.** A leitura dos sensores
> exige o Arduino Nano + PCF8574 + sensores Hall plugados via USB no
> seu PC — algo que o servidor Cloud não tem acesso.

A versão online serve **apenas** para:

- Visualizar o layout, a legenda e o painel antes de montar o hardware
- Mostrar a interface para orientador/banca em revisão remota
- Servir de mockup no artigo/tese (mas use um **screenshot local** com
  sensores ativos, que fica mais convincente)

**Para uso real, siga a seção [Instalação](#-instalação) e rode o app
localmente.**

---

## 📁 Estrutura do repositório

```
Monitor-Bandejas/
│
├── app.py                          # Aplicação Streamlit (ponto de entrada)
├── requirements.txt                # Dependências (Streamlit + pyserial + autorefresh)
├── README.md                       # Este arquivo
├── LICENSE                         # Licença MIT
├── .gitignore                      # Arquivos que não devem ir ao Git
│
├── .streamlit/
│   └── config.toml                 # Tema, telemetria desligada
│
├── firmware/
│   └── RackMonitor_PCF8574.ino     # Sketch do Arduino Nano (8× Hall 3144 + PCF8574)
│
└── docs/
    ├── schematic.png               # Diagrama de ligação Arduino + PCF8574 + Halls
    ├── foto-rack.jpg               # Foto do rack com ímãs (opcional)
    └── screenshot-painel.png       # Screenshot do painel funcionando
```

### Descrição de cada arquivo

| Arquivo | Conteúdo |
|---|---|
| **`app.py`** | Aplicação inteira: thread de leitura serial, estado global via `cache_resource`, render HTML do painel 1×8, sidebar, auto-refresh. ~260 linhas. |
| **`requirements.txt`** | Dependências (Streamlit + pyserial + streamlit-autorefresh). |
| **`README.md`** | Documentação (este arquivo). |
| **`LICENSE`** | Licença MIT. |
| **`.gitignore`** | Ignora `__pycache__/`, `.venv/`, `.streamlit/secrets.toml`. |
| **`firmware/RackMonitor_PCF8574.ino`** | Sketch do Arduino que lê o PCF8574 via I²C e envia as linhas `Canal N: V` terminadas por `---` (ver [Protocolo serial](#-protocolo-serial)). |
| **`docs/`** | Imagens para o README e para o artigo. |

### O que **não** vai no repositório

Gerados em tempo de execução:

```
__pycache__/
.venv/, venv/
*.log                       # Logs de sessão (se você adicionar logging)
.streamlit/secrets.toml
```

---

## 🔧 Hardware

### Diagrama de ligação

```
┌────────────────────┐          ┌────────────────────┐
│  Arduino Nano      │          │  PCF8574           │
│  (ATmega328P)      │          │  (I²C 8-bit I/O)   │
│                    │          │                    │
│  A4 (SDA) ─────────┼──────────┼── SDA              │
│  A5 (SCL) ─────────┼──────────┼── SCL              │
│  5V       ─────────┼──────────┼── VCC              │
│  GND      ─────────┼──────────┼── GND              │
│                    │          │                    │
│  USB ──► PC        │          │  P0 ── Hall H1     │
│  (115200 baud)     │          │  P1 ── Hall H2     │
│                    │          │  P2 ── Hall H3     │
│                    │          │  P3 ── Hall H4     │
│                    │          │  P4 ── Hall H5     │
│                    │          │  P5 ── Hall H6     │
│                    │          │  P6 ── Hall H7     │
│                    │          │  P7 ── Hall H8     │
│                    │          └────────┬───────────┘
└────────────────────┘                   │
                                         │  (8× Hall 3144)
                                    ┌────▼─────┐
                                    │ 3144 #1  │  VCC ── 5V
                                    │ 3144 #2  │  GND ── GND
                                    │   ...    │  OUT ── Px do PCF8574
                                    │ 3144 #8  │  (open-collector)
                                    └──────────┘
```

**Detalhes elétricos:**

- **PCF8574** tem **pull-ups internos fracos** (~100 kΩ). As saídas dos
  Hall 3144 são **open-collector**, então funciona, mas **adicione pull-ups
  externos de 4,7 kΩ a 5V em cada pino** para maior imunidade a ruído
  em bancada.
- **3144** é *unipolar* (detecta polo Sul). Se você usa ímãs de neodímio
  colados na bandeja, garanta que o polo Sul esteja voltado para o sensor.
- **Endereço I²C do PCF8574**: `0x20` (com A0=A1=A2=GND). Se tiver mais
  de um expansor no barramento, ajuste os endereços.

### Lista de materiais (BOM)

| Componente | Especificação | Qtd |
|---|---|---|
| Microcontrolador | Arduino Nano (ATmega328P) | 1 |
| Expansor I²C | PCF8574 (DIP-16 ou módulo) | 1 |
| Sensor Hall | 3144 (unipolar, open-collector) | 8 |
| Pull-ups | 4,7 kΩ (1/4 W) | 8 |
| Ímãs | Neodímio 5×3 mm (ou similar) | 8 |
| Cabo USB | Mini-B ou Micro-B (depende do Nano) | 1 |
| Fios, jumpers | Macho-fêmea | — |

### Layout físico (1 × 8)

O painel do app representa o rack como **1 coluna × 8 linhas**:

- **Bandeja**: 184 × 8 mm (muito larga e fina)
- **Gap vertical**: 10 mm entre bandejas
- **Altura total do rack**: 8 × 8 + 7 × 10 = **134 mm**

Cada bandeja tem um **ímã** colado em uma extremidade, alinhado com o
sensor Hall correspondente no slot `L1..L8`.

---

## 📡 Protocolo serial

O `app.py` **não envia nada** para o Arduino — ele só **lê**. O firmware
do Arduino deve enviar, ciclicamente, um bloco de 8 linhas + terminador:

```
Canal 0: 0
Canal 1: 1
Canal 2: 0
Canal 3: 0
Canal 4: 1
Canal 5: 1
Canal 6: 0
Canal 7: 0
---
```

### Regras que o `app.py` espera

| Padrão | Significado |
|---|---|
| `Canal N: V` (regex `Canal\s+(\d+)\s*:\s*(\d+)`) | Sensor do slot N (0–7) leu o valor V (0 ou 1) |
| Linha começando com `---` | Fim do bloco → os valores são commitados em `leituras` e `ciclos += 1` |
| Qualquer outra linha | Ignorada (bytes são contabilizados no diagnóstico) |

### Interpretação dos valores

| Valor bruto | Estado físico | Cor no painel |
|---|---|---|
| `0` | Ímã **detectado** → **bandeja presente** | 🟢 verde |
| `1` | Sem ímã → **bandeja ausente** | 🔴 vermelho |
| `None` | Ainda sem leitura para esse slot | ⚪ cinza |

**Atenção à lógica invertida**: o sensor Hall 3144 (open-collector) puxa
a saída para **LOW quando detecta ímã**. Por isso `0 = presente`. Se o
seu hardware usar a lógica oposta, ajuste `_slot_html` no `app.py`.

### Firmware mínimo de referência

Se você ainda não tem o sketch, este é o mínimo que satisfaz o protocolo:

```cpp
#include <Wire.h>

#define PCF_ADDR 0x20
#define INTERVALO_MS 200

void setup() {
    Serial.begin(115200);
    Wire.begin();
    // PCF8574 como entrada: escreve 0xFF nos pinos
    Wire.beginTransmission(PCF_ADDR);
    Wire.write(0xFF);
    Wire.endTransmission();
}

void loop() {
    Wire.requestFrom(PCF_ADDR, 1);
    if (Wire.available()) {
        uint8_t estado = Wire.read();   // bit=1 → HIGH (sem ímã); bit=0 → LOW (ímã)
        for (int i = 0; i < 8; i++) {
            Serial.print("Canal ");
            Serial.print(i);
            Serial.print(": ");
            Serial.println((estado >> i) & 0x01);
        }
        Serial.println("---");
    }
    delay(INTERVALO_MS);
}
```

Salve como `firmware/RackMonitor_PCF8574.ino`. Com `INTERVALO_MS = 200`,
o app recebe ~5 ciclos/s — o painel atualiza a cada 300 ms, então você vê
**todos** os ciclos.

---

## ⚙️ Instalação

### Requisitos

- Python **3.10+**
- Windows 10/11, Linux ou macOS
- **Arduino Nano** com firmware gravado
- **Driver CH340** instalado (a maioria dos Nanos usa esse chip USB-serial)
- Cabo USB com **dados** (não apenas carga — cabos "de carregador" não funcionam)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/SEU-USUARIO/monitor-bandejas.git
cd monitor-bandejas

# 2. Ambiente virtual (recomendado)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Grave o firmware no Arduino
#    Abra firmware/RackMonitor_PCF8574.ino no Arduino IDE
#    Selecione a placa "Arduino Nano" + processador "ATmega328P (Old Bootloader)" se for o caso
#    Feche o Monitor Serial ANTES de rodar o Streamlit

# 5. Rode o app
streamlit run app.py
```

O navegador abre automaticamente em `http://localhost:8501`.

### Notas por sistema operacional

**Windows**
- **Feche o Monitor Serial do Arduino IDE** antes de rodar o Streamlit —
  a porta é exclusiva (um `ComPort` aberto por um processo não pode ser
  aberto por outro).
- Se a porta COM **não aparecer** em `serial.tools.list_ports`, instale
  o driver **CH340** (wch.cn → CH341SER). É o chip da maioria dos Nanos
  clonados.
- **Feche outras abas do navegador** com este app aberto — cada aba do
  Streamlit cria uma sessão que pode tentar abrir a porta em paralelo.
  Só a primeira consegue; as demais mostram erro de porta ocupada.

**Linux**
- Adicione seu usuário ao grupo `dialout`:
  ```bash
  sudo usermod -a -G dialout $USER
  # logout e login novamente (ou: newgrp dialout)
  ```
- A porta típica é `/dev/ttyUSB0` (CH340) ou `/dev/ttyACM0` (Nano oficial).

**macOS**
- A porta típica é `/dev/tty.usbserial-XXXX` ou `/dev/cu.usbserial-XXXX`.
- A partir do macOS 13 (Ventura), o driver CH340 é built-in — não precisa
  instalar nada.

---

## 🎮 Uso

### Fluxo básico

1. **Plugue o Arduino** no PC via USB
2. **Feche qualquer outro programa** que use a porta (IDE do Arduino,
   `screen`, `minicom`, `cu`, outra aba do navegador)
3. **Sidebar → Porta serial** — selecione a porta que aparece
   (ex.: `COM5` no Windows, `/dev/ttyUSB0` no Linux)
4. **Sidebar → Baud rate** — `115200` (o firmware de referência usa esse)
5. Clique em **▶ Iniciar**

O app:

- Abre a porta e aguarda **2 s** (auto-reset do Nano após abrir a serial)
- Começa a ler as linhas `Canal N: V` + `---`
- Atualiza o painel a cada **300 ms**
- Incrementa o contador de **Ciclos** a cada bloco completo

### Lendo o painel

- **Barra verde** = bandeja presente (ímã detectado)
- **Barra vermelha** = bandeja ausente
- **Barra cinza** = ainda sem leitura (antes do primeiro ciclo)
- **L1..L8** = identificador do slot
- **`0`/`1`/`—`** = valor bruto no canto direito (para debug)

### Métricas e diagnóstico

- **🟢 Bandejas presentes** — contagem de slots com `0`
- **🔴 Bandejas ausentes** — contagem de slots com `1`
- **⚪ Sem leitura** — contagem de slots com `None`
- **📦 Ciclos** — quantos blocos completos chegaram desde o "Iniciar"
- **🩺 Diagnóstico** — bytes totais, última linha crua (útil para debug do
  firmware) e tabela slot a slot

### Parando

- **⏹ Parar** — sinaliza a thread para encerrar (via `stop_event`) e
  aguarda até 3 s. A porta é fechada.
- **Fechar a aba do navegador** — o Streamlit **não** mata a thread
  (ela é daemon e o processo continua vivo enquanto outra aba/sessão
  usar o app). **Sempre clique em Parar** antes de fechar.

### Dica: múltiplas abas

Abrir o app em **duas abas** cria duas **sessões Streamlit** independentes.
Ambas compartilham o mesmo `E` (graças a `@st.cache_resource`), mas
apenas **uma** pode abrir a porta serial. A segunda aba, ao clicar
"Iniciar", vai ver o erro de porta ocupada.

**Boa prática:** use **uma única aba**. Se quiser monitorar de outra
máquina, use SSH + `streamlit run --server.address 0.0.0.0` (mas a porta
serial é local ao PC que a abriu).

---

## 🩺 Troubleshooting

### "❌ Não foi possível abrir **COM5** após 5 tentativas"

A mensagem do app lista os 5 passos na ordem certa:

1. **Monitor Serial da IDE do Arduino está fechado?** — a porta é exclusiva.
2. **Outra aba do navegador** com este app aberto? — feche-a.
3. **Outro `streamlit run`** em outro terminal? — feche-o.
4. **Desconecte e reconecte o cabo USB** — o CH340 às vezes entra em
   estado zumbi após suspensão do PC.
5. **Reinicie o PC** — último recurso, mas resolve.

### "A porta abriu, mas nenhum dado chegou"

O app detecta isso e avisa. Causas comuns:

- **Baud rate errado** — o firmware usa `115200`, mas você selecionou `9600`.
- **Firmware não envia o terminador `---`** — o app só commita o bloco
  quando vê `---`. Sem ele, `leituras` fica `None`.
- **Nano não está rodando o sketch** — o Monitor Serial mostra algo?
- **Cabo USB de "carregador"** — sem fios de dados. Troque o cabo.

### Sensores invertidos (presente aparece como ausente)

Se sua fiação usa pull-up no pino do PCF8574 em vez de pull-down (ou o
ímã está com o polo Norte voltado para o sensor), a lógica `0=presente`
fica invertida. Duas opções:

1. **Inverter no firmware** — `Serial.println(1 - ((estado >> i) & 1))`
2. **Inverter no app** — troque `if valor == 0` por `if valor == 1` em
   `_slot_html`

### "Permission denied: '/dev/ttyUSB0'" (Linux)

Usuário não está no grupo `dialout`. Veja [Notas por sistema
operacional](#notas-por-sistema-operacional).

### Streamlit recarrega sozinho a cada edição de código

Normal em desenvolvimento. Para produção local, rode com
`streamlit run app.py --server.runOnSave false`.

---

## 🏗️ Notas de arquitetura

### Estado global via `@st.cache_resource`

O `app.py` usa `@st.cache_resource` para persistir `E` (a classe `Estado`)
**entre reruns**. Sem isso, cada clique de botão (que dispara um rerun)
recriaria `E` e perderia a thread e as leituras.

O truque:

```python
@st.cache_resource
def _get_estado(v: int = 1):   # bump `v` se mudar a classe Estado
    return Estado()
```

**Se você editar a classe `Estado`** (adicionar campo, mudar tipo), **bumpe
`v` para 2, 3, ...** — senão o Streamlit pode reaproveitar uma instância
antiga com atributos faltando, gerando `AttributeError` silencioso.

### Thread + lock

- `E.lock` (um `threading.Lock`) protege **todas** as mutações de `E`
  feitas na thread de leitura (`bytes`, `ciclos`, `leituras`, `erro`)
- A UI lê `E.leituras` **com** o lock (`with E.lock:`) — sem isso, você
  pode pegar uma lista pela metade durante o `copy()`
- `E.stop_event` é um `threading.Event` — clicar em Parar faz `set()`,
  e a thread vê `stop.is_set()` no topo do `while` e sai

### Auto-refresh

`st_autorefresh(interval=300, key="refresh")` **só é chamado se
`E.rodando`**. Isso é intencional:

- **Enquanto lê** → refresh a cada 300 ms (painel vivo)
- **Parado** → sem refresh (economiza CPU, e a UI responde a cliques
  imediatamente)

### Por que os slots têm `width:736px;height:32px` fixos?

A proporção física é 184 × 8 mm = **23:1**. Em 4 px/mm:

- 184 mm × 4 = **736 px** de largura
- 8 mm × 4 = **32 px** de altura
- 10 mm × 4 = **40 px** de gap (mas o código usa 30 px — pequeno
  *cheat* para caber melhor em telas de 1080p)

Se você tem monitor 4K e quer **escala 1:1**, aumente para 8 px/mm. Se
quer um painel mais compacto, reduza para 2 px/mm (mas as barras ficam
finas).

---

## ⚠️ Limitações conhecidas

### Do deploy

- **❌ Não funciona no Streamlit Cloud** — sem porta serial USB. Ver
  [Por que não funciona no Cloud](#-por-que-não-funciona-no-cloud).
- **❌ Não funciona em container Docker sem `--device`** — se você
  containerizar, precisa passar `/dev/ttyUSB0` explicitamente.
- **⚠️ Não funciona em rede** — a porta serial é local ao PC que roda o
  Streamlit. Para monitorar de outra máquina, use SSH/port-forward para
  o PC que tem o Arduino plugado.

### Do hardware

- **8 slots fixos** — `NUM_SLOTS = 8` é hard-coded. Para 16 bandejas,
  edite `NUM_SLOTS`, o `buf`, `leituras`, a renderização HTML e o
  firmware.
- **1 coluna × 8 linhas** — o layout assume rack **vertical** (bandejas
  empilhadas). Para layout **horizontal** (2 × 4, 4 × 2, etc.), a
  renderização HTML precisa ser reescrita.
- **PCF8574 não expande além de 8 sensores por chip** — para mais de 8,
  use PCF8575 (16 bits) ou dois PCF8574 com endereços I²C diferentes.

### Do software

- **Sem log persistente** — fechar o app perde o histórico de ciclos e
  leituras. Para gravar, adicione `logging` ou exportação CSV.
- **Sem validação de firmware** — o app confia que o Arduino envia o
  formato esperado. Se o firmware mudar para `CANAL:N:V` (maiúsculas) ou
  `canal N: V` (minúsculas), o regex falha silenciosamente e `leituras`
  fica `None`. O diagnóstico mostra a última linha crua — use para debug.
- **Auto-reset de 2 s** — o `time.sleep(2)` após abrir a serial é para
  o Nano reiniciar após o DTR. Se o seu Nano **não** tem auto-reset,
  reduza esse sleep (ou remova).
- **`use_container_width=True`** em `st.button` — deprecated a partir do
  Streamlit 1.40; o pin `<1.42` mantém funcionando. Para migrar, troque
  por `width="stretch"`.

### Da nuvem

- **Interface visível, hardware inacessível** — o app **abre** no Cloud,
  mas a leitura falha. A interface pode ser útil para **demonstração**,
  mas o screenshot de artigo deve ser feito **localmente** (com sensores
  ativos, painel colorido).

---

## 📚 Referências

Hardware e protocolos:

- **Datasheet PCF8574** — *Remote 8-bit I/O expander for I²C-bus*.
  Texas Instruments. https://www.ti.com/lit/ds/symlink/pcf8574.pdf
- **Datasheet 3144** — *Unipolar Hall-effect sensor*.
  https://www.alldatasheet.com (busque por "3144 Hall")
- **NXP I²C-bus specification** — UM10204.
  https://www.nxp.com/docs/en/user-guide/UM10204.pdf

Streamlit e threading:

- **Streamlit — `st.cache_resource`** — https://docs.streamlit.io/library/api-reference/performance/st.cache_resource
- **Streamlit — `st_autorefresh`** — https://github.com/kmcgrady/streamlit-autorefresh
- **Python `threading`** — https://docs.python.org/3/library/threading.html

Scanner histológico de baixo custo:

- **OpenWSI** — referência open-source de scanner de lâminas:
  https://github.com/AndyFooGuo/OpenWSI
- **OpenFlexure** — referência de microscopia open-hardware:
  https://openflexure.org/

> ⚠️ Verifique datasheets nas fontes primárias antes de citar. A numeração
> 3144 pode variar entre fabricantes (Honeywell, Allegro, clones chineses)
> — confirme a lógica open-collector e a tensão de operação no seu lote.

---

## 🤝 Contribuindo

Sugestões de evolução:

- **Layout configurável** — mover `NUM_SLOTS`, `cols`, `rows` para a
  sidebar (permitir rack 2×4, 4×2, etc.)
- **Exportação CSV** — histórico de mudanças de estado (timestamp,
  slot, estado) para auditoria
- **Alerta sonoro/visual** — detectar bandeja ausente inesperada e piscar
  a barra vermelha
- **Log de conexão** — gravar erros de porta em arquivo para diagnóstico
  pós-incidente
- **Suporte a PCF8575** (16 bits) para racks maiores

## 📄 Licença

Distribuído sob a **licença MIT**. Veja [LICENSE](LICENSE) para o texto
completo. Uso acadêmico e comercial permitido, com atribuição.

## 👤 Autor

**André Rocha**
Doutorando em Ciência da Computação — PGCOMP/UFBA
📧 rocha.a@ufba.br

## 🙏 Agradecimentos

- Meu orientador de Doutorado, Prof. Dr. Luciano Oliveira
- Equipe do Laboratório de Patologia (pela validação do rack em bancada)
- Comunidade open-source do Streamlit, pyserial e Arduino
- [OpenFlexure](https://openflexure.org/) e [OpenWSI](https://github.com/AndyFooGuo/OpenWSI)
  — referências de hardware aberto para patologia digital

---

<p align="center">
  Feito com 🧪 e 🔬 para patologia digital acessível
</p>

# toolbar.py

"""Barra de ferramentas interativa com ícones PNG individuais.

NOTA SOBRE CSS:
    Este arquivo gera um componente que roda em iframe isolado. O
    bloco <style> abaixo aplica-se APENAS ao iframe — não é possível
    centralizá-lo em styles.css (que afeta só a página Streamlit
    principal). Os estilos do iframe precisam ficar aqui por
    arquitetura do Streamlit.

Os ícones são lidos de `images/icons/<nome>.png`. Se ausentes, cai
para o SVG de fallback em _SVG_FALLBACKS.
"""

import base64
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_COMP_DIR = Path(tempfile.gettempdir()) / "histo_toolbar_v2"
_COMP_DIR.mkdir(exist_ok=True)

_ICONS_DIR = Path(__file__).parent / "images" / "icons"

_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { background: transparent; }
  .bar { display: flex; gap: 8px; align-items: center;
         padding: 4px 0; flex-wrap: wrap; }
  .tool {
    border: none; padding: 0; background: transparent; cursor: pointer;
    border-radius: 10px; transition: transform .08s; line-height: 0;
  }
  .tool .icon {
    display: block; height: 44px; width: 44px;
    border-radius: 10px; overflow: hidden;
    background: #e8edf3; box-shadow: 0 0 0 1px #b8b8b8 inset;
    transition: box-shadow .1s;
  }
  .tool .icon img { display:block; width:100%; height:100%; object-fit: cover; }
  .tool .icon svg { display:block; width:100%; height:100%; }
  .tool:hover { transform: translateY(-1px); }
  .tool:hover .icon { box-shadow: 0 0 0 2px #2b7be4 inset; }
  .tool.active .icon { box-shadow: 0 0 0 3px #2b7be4; }
</style>
</head>
<body>
<div class="bar" id="bar"></div>
<script>
(function() {
  const bar = document.getElementById("bar");
  function post(msg) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true }, msg), "*");
  }
  function reportHeight() {
    const h = document.body.scrollHeight || 10;
    post({ type: "streamlit:setFrameHeight", height: Math.max(h, 10) });
  }
  function render(args) {
    const tools = args.tools || [];
    const selected = args.selected || "";
    bar.innerHTML = "";
    tools.forEach(function(t) {
      const btn = document.createElement("button");
      btn.className = "tool" + (selected === t.name ? " active" : "");
      btn.title = t.label || t.name;
      const icon = document.createElement("div");
      icon.className = "icon";
      if (t.icon_b64) {
        const im = document.createElement("img");
        im.src = t.icon_b64;
        im.alt = t.label || t.name;
        icon.appendChild(im);
      } else if (t.svg) {
        icon.innerHTML = t.svg;
      }
      btn.appendChild(icon);
      btn.addEventListener("click", function() {
        post({
          type: "streamlit:setComponentValue",
          value: { tool: t.name, ts: Date.now() },
          dataType: "json"
        });
      });
      bar.appendChild(btn);
    });
    reportHeight();
  }
  window.addEventListener("message", function(e) {
    if (!e.data || e.data.type !== "streamlit:render") return;
    render(e.data.args || {});
  });
  post({ type: "streamlit:componentReady", apiVersion: 1 });
})();
</script>
</body>
</html>
"""

(_COMP_DIR / "index.html").write_text(_HTML, encoding="utf-8")

_toolbar = components.declare_component("histo_toolbar_v2", path=str(_COMP_DIR))


TOOLS = [
    {"name": "rect",       "label": "Retângulo",     "icon": "rect.png"},
    {"name": "ellipse",    "label": "Elipse",        "icon": "ellipse.png"},
    {"name": "freedraw",   "label": "Desenho livre", "icon": "freedraw.png"},
    {"name": "polygon",    "label": "Polígono",      "icon": "polygon.png"},
    {"name": "magic_wand", "label": "Magic Wand",    "icon": "magic_wand.png"},
    {"name": "zoom",       "label": "Zoom / Pan",    "icon": "zoom.png"},
]

_SVG_FALLBACKS = {
    "polygon": """
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <polygon points="22,7 36,17 31,34 13,34 8,17"
                 fill="none" stroke="#37474f" stroke-width="3"
                 stroke-dasharray="4 3" stroke-linejoin="round"/>
      </svg>""",
    "rect": """
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <rect x="8" y="10" width="28" height="24"
              fill="none" stroke="#37474f" stroke-width="3"
              stroke-dasharray="4 3"/>
      </svg>""",
    "ellipse": """
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <ellipse cx="22" cy="22" rx="14" ry="10"
                 fill="none" stroke="#37474f" stroke-width="3"
                 stroke-dasharray="4 3"/>
      </svg>""",
    "freedraw": """
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <path d="M10,30 Q14,10 22,18 T34,26"
              fill="none" stroke="#37474f" stroke-width="3"
              stroke-linecap="round"/>
      </svg>""",
    "magic_wand": """
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <line x1="10" y1="34" x2="28" y2="16"
              stroke="#37474f" stroke-width="4" stroke-linecap="round"/>
        <circle cx="30" cy="14" r="2" fill="#37474f"/>
        <circle cx="24" cy="8" r="1.6" fill="#37474f"/>
        <circle cx="36" cy="10" r="1.6" fill="#37474f"/>
      </svg>""",
    "zoom": """
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <circle cx="19" cy="19" r="10"
                fill="none" stroke="#37474f" stroke-width="3"/>
        <line x1="26" y1="26" x2="36" y2="36"
              stroke="#37474f" stroke-width="3" stroke-linecap="round"/>
        <line x1="15" y1="19" x2="23" y2="19"
              stroke="#37474f" stroke-width="2"/>
        <line x1="19" y1="15" x2="19" y2="23"
              stroke="#37474f" stroke-width="2"/>
      </svg>""",
    "default": """
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <rect x="8" y="8" width="28" height="28"
              fill="none" stroke="#37474f" stroke-width="2"
              stroke-dasharray="3 3"/>
        <text x="22" y="27" text-anchor="middle"
              font-size="16" fill="#37474f"
              font-family="sans-serif">?</text>
      </svg>""",
}


@st.cache_data(show_spinner=False, max_entries=32)
def _icon_b64(path_str: str, mtime: float) -> str:
    """Lê o PNG e retorna data URL base64. Cacheada por (path, mtime)."""
    with open(path_str, "rb") as f:
        data = f.read()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def toolbar(*, selected: str = "magic_wand", key: str = ""):
    """Renderiza a barra. Retorna {tool, ts} ou None."""
    tool_defs = []
    for t in TOOLS:
        td = {"name": t["name"], "label": t["label"]}
        icon_name = t.get("icon")
        loaded = False
        if icon_name:
            p = _ICONS_DIR / icon_name
            if p.exists():
                try:
                    td["icon_b64"] = _icon_b64(
                        str(p), p.stat().st_mtime,
                    )
                    loaded = True
                except OSError:
                    pass
        if not loaded:
            td["svg"] = _SVG_FALLBACKS.get(
                t["name"], _SVG_FALLBACKS["default"],
            )
        tool_defs.append(td)

    return _toolbar(
        tools=tool_defs, selected=selected, key=key, default=None,
    )

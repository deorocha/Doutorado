# clickable.py

"""
Componente mínimo de imagem clicável, com suporte a altura máxima
para caber no viewport sem gerar scroll.
"""
import base64
import tempfile
from pathlib import Path

import cv2
import streamlit.components.v1 as components

_COMP_DIR = Path(tempfile.gettempdir()) / "histo_clickable_image_v3"
_COMP_DIR.mkdir(exist_ok=True)

_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { background: transparent; }
  #wrap { position: relative; width: 100%; }
  #img {
    display: block; cursor: crosshair;
    user-select: none; -webkit-user-drag: none;
  }
</style>
</head>
<body>
<div id="wrap"><img id="img" alt="" /></div>
<script>
(function() {
  const img = document.getElementById("img");

  function post(msg) {
    window.parent.postMessage(
      Object.assign({ isStreamlitMessage: true }, msg), "*"
    );
  }

  function reportHeight() {
    const h = document.body.scrollHeight || 10;
    post({ type: "streamlit:setFrameHeight", height: Math.max(h, 10) });
  }

  function applyStyles(maxHeight) {
    if (maxHeight && maxHeight > 0) {
      img.style.maxHeight = maxHeight + "px";
      img.style.width = "auto";
      img.style.maxWidth = "100%";
      img.style.margin = "0 auto";
    } else {
      img.style.maxHeight = "";
      img.style.width = "100%";
      img.style.height = "auto";
      img.style.margin = "";
    }
  }

  img.addEventListener("load", reportHeight);
  window.addEventListener("resize", reportHeight);

  img.addEventListener("click", function(e) {
    const rect = img.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const sx = img.naturalWidth / rect.width;
    const sy = img.naturalHeight / rect.height;
    const x = Math.round((e.clientX - rect.left) * sx);
    const y = Math.round((e.clientY - rect.top) * sy);
    post({
      type: "streamlit:setComponentValue",
      value: { x: x, y: y, ts: Date.now() },
      dataType: "json"
    });
  });

  window.addEventListener("message", function(e) {
    if (!e.data || e.data.type !== "streamlit:render") return;
    const args = e.data.args || {};
    applyStyles(args.max_height);
    if (args.image_data && img.src !== args.image_data) {
      img.src = args.image_data;
    } else {
      reportHeight();
    }
  });

  post({ type: "streamlit:componentReady", apiVersion: 1 });
})();
</script>
</body>
</html>
"""

(_COMP_DIR / "index.html").write_text(_HTML, encoding="utf-8")

_clickable = components.declare_component(
    "histo_clickable_image_v3",
    path=str(_COMP_DIR),
)


def clickable_image(image_bgr, key=None, max_height=None):
    """
    Renderiza imagem clicável. Retorna {x, y, ts} ou None.

    - max_height: altura máxima em pixels. Quando definido, a imagem é
      reduzida proporcionalmente para caber sem gerar scroll vertical.
    """
    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        return None
    b64 = "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")
    return _clickable(
        image_data=b64,
        key=key,
        default=None,
        max_height=max_height or 0,
    )

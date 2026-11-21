# clickable.py

"""Componente drawable com zoom/pan, magic wand e ferramentas de desenho.

NOTA SOBRE CSS:
    Este arquivo gera um componente em iframe isolado. O bloco <style>
    aplica-se APENAS ao iframe. Não é possível movê-lo para styles.css.
"""

import base64
import json
import tempfile
from pathlib import Path

import cv2
import streamlit.components.v1 as components

_COMP_DIR = Path(tempfile.gettempdir()) / "histo_drawable_image_v9"
_COMP_DIR.mkdir(exist_ok=True)

_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { background: transparent; overflow: hidden; }
  #viewport { position: relative; width: 100%; overflow: hidden;
              background: #1a1a1a; border-radius: 8px; }
  #content { position: relative; display: inline-block;
             transform-origin: 0 0; will-change: transform; }
  #img { display: block; user-select: none; -webkit-user-drag: none;
         pointer-events: none; }
  #canvas { position: absolute; top: 0; left: 0;
            cursor: crosshair; touch-action: none; }
  #canvas.zoom { cursor: grab; }
  #canvas.zoom:active { cursor: grabbing; }
</style>
</head>
<body>
<div id="viewport"><div id="content">
  <img id="img" alt="" /><canvas id="canvas"></canvas>
</div></div>
<script>
(function() {
  const viewport = document.getElementById("viewport");
  const content  = document.getElementById("content");
  const img      = document.getElementById("img");
  const canvas   = document.getElementById("canvas");
  const ctx      = canvas.getContext("2d");

  const state = {
    scale: 1, tx: 0, ty: 0, tool: "magic_wand",
    thickness: 2,
    borderColor: "#00b300",
    drawing: false, panning: false, panStart: null,
    startX: 0, startY: 0, curX: 0, curY: 0,
    currentPath: [], polygonPoints: [], hoverPoint: null,
    existingRegions: [], previewPendingRegion: null,
    zoomKey: "zoom_default", _zoomLoaded: false,
  };

  function post(m) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true }, m), "*");
  }
  function reportHeight() {
    const h = viewport.getBoundingClientRect().height + 4;
    post({ type: "streamlit:setFrameHeight", height: Math.max(h, 10) });
  }
  function emit(v) {
    v.ts = Date.now();
    post({ type: "streamlit:setComponentValue", value: v, dataType: "json" });
  }
  function applyTransform() {
    content.style.transform =
      `translate(${state.tx}px, ${state.ty}px) scale(${state.scale})`;
  }
  function saveZoom() {
    try {
      sessionStorage.setItem(state.zoomKey, JSON.stringify(
        { scale: state.scale, tx: state.tx, ty: state.ty }));
    } catch(e) {}
  }
  function loadZoom() {
    try {
      const s = sessionStorage.getItem(state.zoomKey);
      if (s) {
        const z = JSON.parse(s);
        state.scale = z.scale || 1;
        state.tx = z.tx || 0;
        state.ty = z.ty || 0;
      }
    } catch(e) {}
  }
  function screenToImage(cx, cy) {
    const r = canvas.getBoundingClientRect();
    return {
      x: (cx - r.left) * (canvas.width  / r.width),
      y: (cy - r.top)  * (canvas.height / r.height),
    };
  }

  // Luminância relativa (sRGB) — decide texto preto vs branco
  function hexLuminance(hex) {
    const h = (hex || "").replace("#", "");
    if (h.length !== 6) return 0.5;
    const r = parseInt(h.substr(0, 2), 16) / 255;
    const g = parseInt(h.substr(2, 2), 16) / 255;
    const b = parseInt(h.substr(4, 2), 16) / 255;
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function drawOutline(r, color, dash, extraThick) {
    ctx.strokeStyle = color;
    ctx.lineWidth = state.thickness + (extraThick || 0);
    ctx.setLineDash(dash || [8, 6]);
    if (r.contour && r.contour.length > 1) {
      ctx.beginPath();
      ctx.moveTo(r.contour[0][0], r.contour[0][1]);
      for (let i = 1; i < r.contour.length; i++)
        ctx.lineTo(r.contour[i][0], r.contour[i][1]);
      ctx.closePath(); ctx.stroke();
    } else if (r.x !== undefined) {
      ctx.strokeRect(r.x, r.y, r.w, r.h);
    }
  }

  // Pill colorida com número, texto contrastante (preto/branco).
  function drawNumber(r, n) {
    ctx.save();
    const fs = Math.max(20, Math.floor(canvas.width / 60));
    ctx.font = "bold " + fs + "px 'Segoe UI', Arial, sans-serif";
    const label = "#" + n;
    const textW = ctx.measureText(label).width;
    const padX = Math.round(fs * 0.55);
    const padY = Math.round(fs * 0.35);
    const boxW = textW + padX * 2;
    const boxH = fs + padY * 2;

    const rx = (r.x || 0);
    const ry = (r.y || 0);
    let bx = rx + Math.round(fs * 0.2);
    let by = ry - boxH - Math.round(fs * 0.15);
    if (by < 0) by = ry + Math.round(fs * 0.15);

    const radius = boxH / 2;
    ctx.beginPath();
    ctx.moveTo(bx + radius, by);
    ctx.lineTo(bx + boxW - radius, by);
    ctx.arcTo(bx + boxW, by, bx + boxW, by + radius, radius);
    ctx.lineTo(bx + boxW, by + boxH - radius);
    ctx.arcTo(bx + boxW, by + boxH, bx + boxW - radius, by + boxH, radius);
    ctx.lineTo(bx + radius, by + boxH);
    ctx.arcTo(bx, by + boxH, bx, by + boxH - radius, radius);
    ctx.lineTo(bx, by + radius);
    ctx.arcTo(bx, by, bx + radius, by, radius);
    ctx.closePath();

    ctx.fillStyle = state.borderColor;
    ctx.fill();
    ctx.lineWidth = Math.max(1.5, fs * 0.08);
    ctx.strokeStyle = "rgba(0,0,0,0.55)";
    ctx.stroke();

    const lum = hexLuminance(state.borderColor);
    ctx.fillStyle = lum > 0.55 ? "#0a0a0a" : "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, bx + boxW / 2,
                 by + boxH / 2 + Math.round(fs * 0.04));
    ctx.restore();
  }

  function redraw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Regiões aceitas: cor escolhida, dash [8,6], com número
    state.existingRegions.forEach((r, idx) => {
      if (r.kind === "point") {
        const rad = Math.max(5, canvas.width / 280);
        ctx.beginPath();
        ctx.arc(r.x, r.y, rad, 0, 2*Math.PI);
        ctx.fillStyle = state.borderColor;
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.55)";
        ctx.lineWidth = Math.max(1, state.thickness);
        ctx.stroke();
      } else {
        drawOutline(r, state.borderColor);
      }
      drawNumber(r, idx + 1);
    });

    // Pendente (Magic Wand): cor escolhida, dash mais curto [6,4],
    // levemente mais espessa para destacar. Sem número.
    if (state.previewPendingRegion) {
      drawOutline(state.previewPendingRegion,
                  state.borderColor, [6, 4], 1);
    }

    // Traço em andamento (rect/ellipse/freedraw): cor escolhida,
    // dash [4,4] para indicar "temporário".
    if (state.drawing) {
      ctx.strokeStyle = state.borderColor;
      ctx.lineWidth = state.thickness;
      ctx.setLineDash([4, 4]);
      if (state.tool === "rect") {
        const x = Math.min(state.startX, state.curX);
        const y = Math.min(state.startY, state.curY);
        const w = Math.abs(state.curX - state.startX);
        const h = Math.abs(state.curY - state.startY);
        ctx.strokeRect(x, y, w, h);
      } else if (state.tool === "ellipse") {
        const x = Math.min(state.startX, state.curX);
        const y = Math.min(state.startY, state.curY);
        const w = Math.abs(state.curX - state.startX);
        const h = Math.abs(state.curY - state.startY);
        ctx.beginPath();
        ctx.ellipse(x+w/2, y+h/2, w/2, h/2, 0, 0, 2*Math.PI);
        ctx.stroke();
      } else if (state.tool === "freedraw" && state.currentPath.length) {
        ctx.beginPath();
        ctx.moveTo(state.currentPath[0].x, state.currentPath[0].y);
        for (let i = 1; i < state.currentPath.length; i++)
          ctx.lineTo(state.currentPath[i].x, state.currentPath[i].y);
        ctx.stroke();
      }
    }

    // Polígono em construção: cor escolhida, dash [8,6];
    // vértices numerados (primeiro = vermelho como fechador).
    if (state.tool === "polygon" && state.polygonPoints.length) {
      ctx.strokeStyle = state.borderColor;
      ctx.lineWidth = state.thickness;
      ctx.setLineDash([8, 6]); ctx.beginPath();
      ctx.moveTo(state.polygonPoints[0].x, state.polygonPoints[0].y);
      for (let i = 1; i < state.polygonPoints.length; i++)
        ctx.lineTo(state.polygonPoints[i].x, state.polygonPoints[i].y);
      if (state.hoverPoint)
        ctx.lineTo(state.hoverPoint.x, state.hoverPoint.y);
      ctx.stroke(); ctx.setLineDash([]);
      state.polygonPoints.forEach((p, i) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, i === 0 ? 6 : 4, 0, 2*Math.PI);
        ctx.fillStyle = i === 0 ? "#e53935" : state.borderColor;
        ctx.fill();
      });
    }
  }

  function bbox(points) {
    let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
    points.forEach(p => {
      if (p.x<x0) x0=p.x; if (p.x>x1) x1=p.x;
      if (p.y<y0) y0=p.y; if (p.y>y1) y1=p.y;
    });
    return { x:Math.round(x0), y:Math.round(y0),
             w:Math.round(x1-x0), h:Math.round(y1-y0) };
  }
  function simplify(points, tol) {
    if (points.length < 3) return points;
    const out = [points[0]];
    for (let i = 1; i < points.length; i++) {
      const p = out[out.length-1], c = points[i];
      if (Math.hypot(c.x-p.x, c.y-p.y) >= tol) out.push(c);
    }
    const last = points[points.length-1];
    if (out[out.length-1] !== last) out.push(last);
    return out;
  }

  // --- zoom ---
  canvas.addEventListener("wheel", function(e) {
    e.preventDefault();
    const oldS = state.scale;
    const newS = Math.max(0.1, Math.min(20,
      oldS * (e.deltaY < 0 ? 1.12 : 1/1.12)));
    const r = viewport.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    state.tx = mx - (mx - state.tx) * (newS / oldS);
    state.ty = my - (my - state.ty) * (newS / oldS);
    state.scale = newS;
    applyTransform(); saveZoom();
  }, { passive: false });

  // --- mouse ---
  canvas.addEventListener("mousedown", function(e) {
    if (e.button === 1 || state.tool === "zoom") {
      state.panning = true;
      state.panStart = { x: e.clientX - state.tx, y: e.clientY - state.ty };
      e.preventDefault(); return;
    }
    if (e.button !== 0) return;
    if (["magic_wand", "point", "polygon"].includes(state.tool)) return;
    const p = screenToImage(e.clientX, e.clientY);
    state.drawing = true;
    state.startX = p.x; state.startY = p.y;
    state.curX = p.x;  state.curY = p.y;
    state.currentPath = [p];
    redraw();
  });
  canvas.addEventListener("mousemove", function(e) {
    if (state.panning) {
      state.tx = e.clientX - state.panStart.x;
      state.ty = e.clientY - state.panStart.y;
      applyTransform(); saveZoom(); return;
    }
    const p = screenToImage(e.clientX, e.clientY);
    if (state.tool === "polygon" && state.polygonPoints.length) {
      state.hoverPoint = p; redraw(); return;
    }
    if (!state.drawing) return;
    state.curX = p.x; state.curY = p.y;
    if (state.tool === "freedraw") state.currentPath.push(p);
    redraw();
  });
  window.addEventListener("mouseup", function(e) {
    if (state.panning) { state.panning = false; return; }
    if (!state.drawing) return;
    state.drawing = false;
    const p = screenToImage(e.clientX, e.clientY);
    if (state.tool === "rect" || state.tool === "ellipse") {
      const x = Math.min(state.startX, p.x);
      const y = Math.min(state.startY, p.y);
      const w = Math.abs(p.x - state.startX);
      const h = Math.abs(p.y - state.startY);
      if (w < 3 || h < 3) { redraw(); return; }
      if (state.tool === "rect") {
        emit({ action:"region", kind:"rect",
               x: Math.round(x), y: Math.round(y),
               w: Math.round(w), h: Math.round(h) });
      } else {
        emit({ action:"region", kind:"ellipse",
               x: Math.round(x), y: Math.round(y),
               w: Math.round(w), h: Math.round(h),
               cx: Math.round(x+w/2), cy: Math.round(y+h/2),
               rx: Math.round(w/2), ry: Math.round(h/2) });
      }
    } else if (state.tool === "freedraw") {
      state.currentPath.push(p);
      const pts = simplify(state.currentPath, 2);
      if (pts.length < 3) { state.currentPath = []; redraw(); return; }
      const b = bbox(pts);
      emit({ action:"region", kind:"freedraw",
             points: pts.map(q => [Math.round(q.x), Math.round(q.y)]),
             x: b.x, y: b.y, w: b.w, h: b.h });
    }
    state.currentPath = []; redraw();
  });

  canvas.addEventListener("click", function(e) {
    if (state.tool === "zoom") return;
    const p = screenToImage(e.clientX, e.clientY);
    if (state.tool === "point") {
      emit({ action:"region", kind:"point",
             x: Math.round(p.x), y: Math.round(p.y), w: 1, h: 1 });
      return;
    }
    if (state.tool === "magic_wand") {
      emit({ action:"magic_wand",
             x: Math.round(p.x), y: Math.round(p.y) });
      return;
    }
    if (state.tool === "polygon") {
      if (state.polygonPoints.length >= 3) {
        const f = state.polygonPoints[0];
        if (Math.hypot(f.x - p.x, f.y - p.y) < 15) {
          const b = bbox(state.polygonPoints);
          emit({ action:"region", kind:"polygon",
                 points: state.polygonPoints.map(
                   q => [Math.round(q.x), Math.round(q.y)]),
                 x: b.x, y: b.y, w: b.w, h: b.h });
          state.polygonPoints = []; state.hoverPoint = null;
          redraw(); return;
        }
      }
      state.polygonPoints.push(p);
      redraw();
    }
  });
  canvas.addEventListener("dblclick", function(e) {
    if (state.tool === "polygon" && state.polygonPoints.length >= 3) {
      const b = bbox(state.polygonPoints);
      emit({ action:"region", kind:"polygon",
             points: state.polygonPoints.map(
               q => [Math.round(q.x), Math.round(q.y)]),
             x: b.x, y: b.y, w: b.w, h: b.h });
      state.polygonPoints = []; state.hoverPoint = null; redraw();
    }
  });

  // --- render from Streamlit ---
  window.addEventListener("message", function(e) {
    if (!e.data || e.data.type !== "streamlit:render") return;
    const args = e.data.args || {};
    state.tool = args.tool || "magic_wand";
    state.thickness = args.thickness || 2;
    state.borderColor = args.border_color || "#00b300";
    canvas.classList.toggle("zoom", state.tool === "zoom");
    if (args.zoom_key) state.zoomKey = args.zoom_key;

    if (args.image_data && img.src !== args.image_data) {
      img.onload = function() {
        canvas.width  = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const maxH = args.max_height || 0;
        if (maxH > 0 && img.naturalHeight > maxH) {
          const r = maxH / img.naturalHeight;
          img.style.width  = (img.naturalWidth * r) + "px";
          img.style.height = maxH + "px";
        } else {
          img.style.width  = img.naturalWidth  + "px";
          img.style.height = img.naturalHeight + "px";
        }
        canvas.style.width  = img.style.width;
        canvas.style.height = img.style.height;
        setTimeout(function() {
          viewport.style.height =
            (content.getBoundingClientRect().height * state.scale + 4) + "px";
          reportHeight(); redraw();
        }, 30);
      };
      img.src = args.image_data;
    }
    try { state.existingRegions = JSON.parse(args.existing_regions || "[]"); }
    catch(e) { state.existingRegions = []; }
    try {
      state.previewPendingRegion = args.pending_region
        ? JSON.parse(args.pending_region) : null;
    } catch(e) { state.previewPendingRegion = null; }
    if (!state._zoomLoaded) {
      loadZoom(); applyTransform(); state._zoomLoaded = true;
    }
    redraw();
  });

  post({ type: "streamlit:componentReady", apiVersion: 1 });
})();
</script>
</body>
</html>
"""

(_COMP_DIR / "index.html").write_text(_HTML, encoding="utf-8")

_drawable = components.declare_component(
    "histo_drawable_image_v9", path=str(_COMP_DIR),
)


def drawable_image(
    image_bgr, key=None, tool="magic_wand",
    existing_regions=None, pending_region=None, max_height=None,
    thickness=2, border_color="#00b300",
):
    """Componente drawable — retorna ação ou None.

    - thickness:    espessura (px, em coords da imagem) das bordas tracejadas.
    - border_color: cor (hex) usada nas regiões aceitas, na pendente do
                    Magic Wand, no traço em andamento e no polígono.
    """
    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        return None
    b64 = "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")
    return _drawable(
        image_data=b64,
        tool=tool,
        existing_regions=json.dumps(existing_regions or []),
        pending_region=json.dumps(pending_region) if pending_region else "",
        max_height=max_height or 0,
        thickness=int(thickness),
        border_color=border_color,
        zoom_key=key or "default",
        key=key,
        default=None,
    )

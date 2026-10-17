# processing.py

import cv2
import numpy as np


def detect_regions(image_bgr: np.ndarray, params: dict):
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]

    tissue = ((sat > params["sat_threshold"]) |
              (val < params["val_threshold"])).astype(np.uint8) * 255

    gray  = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, params["canny_low"], params["canny_high"])

    combined = cv2.bitwise_or(tissue, edges)

    k = params["morph_kernel"]
    if k % 2 == 0:
        k += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    H, W = image_bgr.shape[:2]
    pad = params["padding"]
    regions = []

    for c in contours:
        if cv2.contourArea(c) < params["min_area"]:
            continue

        # Contorno simplificado (aproximação poligonal) — usado só para desenho
        eps = 0.005 * cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)

        # BBox com padding (usado pelo scanner para capturar o tile)
        x, y, w, h = cv2.boundingRect(c)
        x = max(0, x - pad)
        y = max(0, y - pad)
        w = min(W - x, w + 2 * pad)
        h = min(H - y, h + 2 * pad)

        regions.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "contour": approx.tolist(),   # lista de [x, y]
        })

    regions.sort(key=lambda r: (r["y"] // 150, r["x"]))
    return regions, closed


def _draw_dashed_polyline(img, pts, color, thickness=1,
                          dash_len=10, gap_len=8):
    """Desenha polilinha fechada em estilo tracejado."""
    pts = np.asarray(pts, dtype=np.float32)
    n = len(pts)
    if n < 2:
        return
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        seg = p2 - p1
        dist = float(np.linalg.norm(seg))
        if dist < 1e-3:
            continue
        unit = seg / dist
        pos = 0.0
        while pos < dist:
            end = min(pos + dash_len, dist)
            a = tuple((p1 + unit * pos).astype(int))
            b = tuple((p1 + unit * end).astype(int))
            cv2.line(img, a, b, color, thickness, cv2.LINE_AA)
            pos = end + gap_len


def draw_regions(image_bgr, regions, color=(0, 255, 0), thickness=1):
    """Desenha as regiões como contornos tracejados (fallback: bbox tracejada)."""
    vis = image_bgr.copy()
    for i, r in enumerate(regions, 1):
        if r.get("contour"):
            pts = r["contour"]
        else:
            x, y, w, h = r["x"], r["y"], r["w"], r["h"]
            pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]

        _draw_dashed_polyline(vis, pts, color, thickness)

        tx = r["x"]
        ty = max(20, r["y"] - 8)
        cv2.putText(vis, f"#{i}", (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return vis


def magic_wand_flood_fill(img_bgr, seed_x, seed_y, threshold,
                          padding=0, contiguous=True, preprocess=None):
    """
    Magic Wand estilo Photoshop.

    - threshold:  distância máx. de cor (Lab, escala OpenCV 0–255)
                  entre o pixel clicado e os vizinhos aceitos.
    - padding:    expande a borda em N px.
    - contiguous: se True, só o blob conectado ao clique.
    - preprocess: None ou "clahe" (realça contraste antes da comparação).
    """
    H, W = img_bgr.shape[:2]
    if not (0 <= seed_x < W and 0 <= seed_y < H):
        return None, np.zeros((H, W), np.uint8)

    # --- CLAHE opcional (endereça "imagens esmaecidas") ---
    work = img_bgr
    if preprocess == "clahe":
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        work = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    img_lab = cv2.cvtColor(work, cv2.COLOR_BGR2LAB).astype(np.int32)
    seed_color = img_lab[seed_y, seed_x]

    diff = img_lab - seed_color
    dist = np.sqrt((diff * diff).sum(axis=2))
    similar = (dist <= threshold).astype(np.uint8)

    if contiguous:
        ff = np.zeros((H + 2, W + 2), np.uint8)
        cv2.floodFill(similar, ff, (seed_x, seed_y), 2)
        mask = (similar == 2).astype(np.uint8) * 255
    else:
        mask = similar * 255

    if padding > 0:
        k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (padding * 2 + 1, padding * 2 + 1)
        )
        mask = cv2.dilate(mask, k)

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return None, mask

    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 1:
        return None, mask

    x, y, w, h = cv2.boundingRect(c)
    eps = 0.005 * cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
    area_px = int((mask > 0).sum())

    return {
        "x": int(x), "y": int(y), "w": int(w), "h": int(h),
        "contour": approx.tolist(),
        "area_px": area_px,
    }, mask


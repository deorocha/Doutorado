# qr_utils.py

import cv2
import numpy as np
import qrcode

def read_qr(image_bgr: np.ndarray):
    """Retorna (dados, pontos) do QR-Code. Tenta upscale se falhar."""
    det = cv2.QRCodeDetector()
    data, pts, _ = det.detectAndDecode(image_bgr)
    if data:
        return data, pts
    big = cv2.resize(image_bgr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    data, pts, _ = det.detectAndDecode(big)
    if data and pts is not None:
        pts = pts / 2.0
    return data or None, pts

def make_qr_image(data: str, size: int = 220) -> np.ndarray:
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

# demo.py

import cv2
import numpy as np
from qr_utils import make_qr_image

def generate_demo_slide(qr_data: str, size=(1600, 900)) -> np.ndarray:
    W, H = size
    img = np.full((H, W, 3), 245, dtype=np.uint8)

    rng = np.random.default_rng(abs(hash(qr_data)) % (2**32))
    for _ in range(rng.integers(3, 7)):
        cx = int(rng.integers(150, W - 150))
        cy = int(rng.integers(150, H - 150))
        rx = int(rng.integers(60, 160))
        ry = int(rng.integers(60, 160))
        color = (int(rng.integers(120, 170)),
                 int(rng.integers(60,  110)),
                 int(rng.integers(160, 200)))  # BGR ~ rosa/roxo
        cv2.ellipse(img, (cx, cy), (rx, ry),
                    float(rng.integers(0, 180)), 0, 360, color, -1)

    qr = make_qr_image(qr_data, size=180)
    img[15:15 + qr.shape[0], W - qr.shape[1] - 15:W - 15] = qr
    return img

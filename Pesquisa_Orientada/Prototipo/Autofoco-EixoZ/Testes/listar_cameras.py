import cv2

print("Testando índices 0..5 (pode demorar ~1s por índice)...\n")
encontradas = []
for i in range(6):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # CAP_DSHOW acelera no Windows
    if cap.isOpened():
        ok, frame = cap.read()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            print(f"Índice {i}: OK — resolução {w}x{h}")
            encontradas.append(i)
        else:
            print(f"Índice {i}: abriu mas não leu frame")
    else:
        print(f"Índice {i}: indisponível")
    cap.release()

print(f"\nCâmeras disponíveis: {encontradas}")
print("Use no Streamlit o índice da câmera do scanner.")

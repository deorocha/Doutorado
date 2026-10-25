import time
import cv2
import serial
import serial.tools.list_ports

print("=" * 62)
print("DIAGNÓSTICO COMPLETO DO HARDWARE")
print("=" * 62)

# ---------- 1) Câmeras ----------
print("\n[1] Câmeras (índices 0..5)")
cams_ok = []
for i in range(6):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"    índice {i}: OK   ({frame.shape[1]}x{frame.shape[0]})")
            cams_ok.append(i)
        else:
            print(f"    índice {i}: abriu mas não leu frame")
    else:
        print(f"    índice {i}: indisponível")
    cap.release()
if not cams_ok:
    print("    ⚠ NENHUMA CÂMERA ABRIU. Verifique:")
    print("      - Câmera conectada? Outro app usando? (Câmera do Windows,")
    print("        Teams, Zoom, OBS). Feche-os antes de rodar.")

# ---------- 2) Portas seriais ----------
print("\n[2] Portas seriais disponíveis")
portas = list(serial.tools.list_ports.comports())
if not portas:
    print("    NENHUMA PORTA ENCONTRADA")
    print("    → Driver CH340 instalado? Cabo USB com dados?")
else:
    for p in portas:
        print(f"    {p.device:<10s} — {p.description}")

# ---------- 3) PING em cada porta ----------
print("\n[3] Testando PING em cada porta (1.5 s cada)")
esp_ok_em = None
for p in portas:
    print(f"\n    --- {p.device} ---")
    try:
        s = serial.Serial()
        s.port = p.device
        s.baudrate = 115200
        s.timeout = 0.3
        s.dtr = False
        s.rts = False
        s.open()
        time.sleep(0.6)
        s.reset_input_buffer()
        s.write(b"PING\n")
        s.write(b"$102?\n")
        time.sleep(0.8)
        got = []
        while s.in_waiting:
            line = s.readline().decode(errors="ignore").strip()
            if line:
                got.append(line)
                print(f"        RECV: {line!r}")
        s.close()

        if "PONG" in got or any(l.startswith("$102=") for l in got):
            print(f"        ✅ ESP ENCONTRADO em {p.device}")
            esp_ok_em = p.device
        elif got:
            print(f"        ⚠ respondeu algo, mas não PONG/$102")
        else:
            print(f"        ❌ silêncio total")
    except Exception as e:
        print(f"        ERRO: {e}")

print("\n" + "=" * 62)
print("RESUMO")
print("=" * 62)
print(f"  Câmera OK nos índices: {cams_ok or 'nenhum'}")
print(f"  ESP respondeu em:     {esp_ok_em or 'nenhuma porta'}")
if esp_ok_em:
    print(f"\n  → No Streamlit, use:  porta = {esp_ok_em}")
if cams_ok:
    print(f"  → No Streamlit, use:  câmera = {cams_ok[0]}")

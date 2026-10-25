import time
import serial

def open_robust(port, baud=115200, attempts=3):
    for i in range(attempts):
        try:
            return serial.Serial(port=port, baudrate=baud, timeout=1)
        except OSError as e:
            print(f"  tentativa {i+1}: {e}")
            time.sleep(0.5)
    raise RuntimeError("Falhou todas")

print("Abrindo COM5...")
s = open_robust("COM5")
print("✅ Aberto")

time.sleep(2.0)
s.reset_input_buffer()

print("Enviando PING...")
s.write(b"PING\n$102?\n")
time.sleep(0.8)
while s.in_waiting:
    line = s.readline().decode(errors="ignore").strip()
    if line:
        print(f"  RECV: {line!r}")

s.close()

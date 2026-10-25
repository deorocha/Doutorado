import serial, serial.tools.list_ports, time

print("=== Portas disponíveis ===")
for p in serial.tools.list_ports.comports():
    print(f"  {p.device}  —  {p.description}")

port = input("\nPorta do ESP (ex: COM4): ").strip()
ser = serial.Serial(port, 115200, timeout=1)
try:
    ser.setDTR(False); ser.setRTS(False)   # evita reset
except Exception:
    pass

print("\n[1] Lendo 15 s de mensagens de boot...")
t0 = time.time(); bootloop = 0
while time.time() - t0 < 15:
    line = ser.readline().decode(errors="ignore").strip()
    if line:
        print(f"   {line!r}")
        if "rst cause" in line or line.startswith("ets"):
            bootloop += 1

print(f"\n[2] Enviando '$102?'...")
ser.write(b"$102?\n")
t0 = time.time(); got_spm = False
while time.time() - t0 < 5:
    line = ser.readline().decode(errors="ignore").strip()
    if line:
        print(f"   {line!r}")
        if line.startswith("$102="):
            got_spm = True

print(f"\n[3] Enviando 'Z0.0000'...")
ser.write(b"Z0.0000\n")
t0 = time.time(); got_ok = False
while time.time() - t0 < 10:
    line = ser.readline().decode(errors="ignore").strip()
    if line:
        print(f"   {line!r}")
        if line == "ok":
            got_ok = True

ser.close()

print("\n=== RESULTADO ===")
print(f"  $102 respondido: {got_spm}")
print(f"  Z respondido:    {got_ok}")
print(f"  Bootloop visto:  {'SIM' if bootloop > 2 else 'não'}")
if not got_spm and not got_ok:
    print("→ Firmware NÃO está respondendo. Ver Passo 2/3.")
elif got_spm and got_ok:
    print("→ Hardware OK. O problema é DTR/reset ou porta no Streamlit.")

import serial, time

port = input("Porta COM do ESP (ex: COM5): ").strip()

# Abre sem resetar
s = serial.Serial()
s.port = port; s.baudrate = 115200; s.timeout = 1
s.dtr = False; s.rts = False
s.open()
time.sleep(0.5)
s.reset_input_buffer()

print(f"\nAberto em {port}. Enviando PING a cada 500 ms por 5 s...\n")
for i in range(10):
    s.write(b"PING\n$102?\n")
    time.sleep(0.5)
    while s.in_waiting or True:
        line = s.readline().decode(errors="ignore").strip()
        if not line:
            break
        print(f"  [{i:02d}] {line!r}")

s.close()

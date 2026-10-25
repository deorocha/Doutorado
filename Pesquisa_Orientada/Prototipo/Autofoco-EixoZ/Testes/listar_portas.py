import serial.tools.list_ports

portas = list(serial.tools.list_ports.comports())
if not portas:
    print("Nenhuma porta serial encontrada. Arduino conectado?")
for p in portas:
    print(f"{p.device}  —  {p.description}  —  {p.hwid}")

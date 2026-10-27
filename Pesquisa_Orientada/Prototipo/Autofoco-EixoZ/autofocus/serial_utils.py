"""Abertura robusta de porta serial (contorna OSError(22) do CH340)."""
from __future__ import annotations

import time
from typing import Optional

try:
    import serial as pyserial
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False


def open_serial_robust(port: str, baud: int = 115200,
                       timeout: float = 1.0,
                       attempts: int = 3) -> "pyserial.Serial":
    if not HAS_PYSERIAL:
        raise ImportError("Instale pyserial: pip install pyserial")

    last_err: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return pyserial.Serial(port=port, baudrate=baud, timeout=timeout)
        except OSError as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(0.5)

    try:
        ser = pyserial.Serial()
        ser.port = port
        ser.baudrate = baud
        ser.timeout = timeout
        ser.dtr = False
        ser.rts = False
        ser.open()
        return ser
    except OSError as e:
        last_err = e

    raise RuntimeError(
        f"Não foi possível abrir {port} ({baud} baud).\n"
        f"Erro: {last_err}\n\n"
        f"Verifique na ordem:\n"
        f"  1. Monitor Serial do Arduino IDE FECHADO?\n"
        f"  2. Cura, Pronterface, VSCode/PlatformIO — algum aberto?\n"
        f"  3. Desconecte e reconecte o cabo USB.\n"
        f"  4. Tente outra porta USB (traseira, direto na placa-mãe).\n"
        f"  5. Reinstale o driver CH340 (wch.cn → CH341SER).\n"
        f"  6. Reinicie o PC."
    ) from last_err

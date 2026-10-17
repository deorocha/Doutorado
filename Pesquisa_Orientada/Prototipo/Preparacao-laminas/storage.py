# storage.py

import json
from config import STATE_FILE, DATA_DIR

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"slides": {}}

def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    tmp.replace(STATE_FILE)

def get_slide(state: dict, tray: int, pos: int) -> dict:
    key = f"T{tray:02d}-S{pos:02d}"
    return state["slides"].get(key, {
        "tray": tray, "position": pos, "status": "empty",
        "qr_id": None, "scan_mode": None, "regions": [], "params": {},
    })

def update_slide(state: dict, tray: int, pos: int, updates: dict) -> None:
    key = f"T{tray:02d}-S{pos:02d}"
    slide = state["slides"].get(key) or {"tray": tray, "position": pos}
    slide.update(updates)
    state["slides"][key] = slide
    save_state(state)

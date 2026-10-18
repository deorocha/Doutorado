# storage.py

import json
from config import STATE_FILE, DATA_DIR, slide_key


def _migrate_keys(state: dict) -> dict:
    """Renomeia chaves 'Txx-Syy' (versão antiga) para 'Bxx-Lyy'."""
    if "slides" not in state:
        return state
    new_slides = {}
    for key, val in state["slides"].items():
        new_key = key
        if key.startswith("T") and "-S" in key:
            parts = key.split("-")
            if len(parts) == 2:
                new_key = "B" + parts[0][1:] + "-L" + parts[1][1:]
        new_slides[new_key] = val
    state["slides"] = new_slides
    return state


def load_state() -> dict:
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        return _migrate_keys(state)
    return {"slides": {}}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    tmp.replace(STATE_FILE)


def get_slide(state: dict, tray: int, pos: int) -> dict:
    key = slide_key(tray, pos)
    return state["slides"].get(key, {
        "tray": tray, "position": pos, "status": "empty",
        "qr_id": None, "scan_mode": None, "regions": [], "params": {},
    })


def update_slide(state: dict, tray: int, pos: int, updates: dict) -> None:
    key = slide_key(tray, pos)
    slide = state["slides"].get(key) or {"tray": tray, "position": pos}
    slide.update(updates)
    state["slides"][key] = slide
    save_state(state)

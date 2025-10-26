import os, time
PAUSE_FILE = ".agent_pause"

def is_paused():
    return os.path.exists(PAUSE_FILE)

def set_paused(flag: bool):
    if flag: open(PAUSE_FILE, "w").close()
    else:
        try: os.remove(PAUSE_FILE)
        except FileNotFoundError: pass

import webbrowser
import time
import sys
import os
import threading
import importlib
import socket


def porta_disponivel(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0


def encontrar_porta(inicio=5003, fim=5020):
    for p in range(inicio, fim):
        if porta_disponivel(p):
            return p
    return inicio


def abrir_browser(port):
    # Espera o servidor estar pronto
    for _ in range(30):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    break
        except Exception:
            pass
        time.sleep(0.5)
    time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

    port = encontrar_porta()
    os.environ["PORT"] = str(port)

    t = threading.Thread(target=abrir_browser, args=(port,), daemon=True)
    t.start()

    module = importlib.import_module("app")
    module.app.run(debug=False, host="127.0.0.1", port=port, use_reloader=False)
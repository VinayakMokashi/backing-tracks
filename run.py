"""Launch the Key Shifter server and open the browser."""
import threading
import webbrowser

import uvicorn

import config


def _open_browser() -> None:
    webbrowser.open_new_tab(f"http://{config.HOST}:{config.PORT}/")


if __name__ == "__main__":
    config.ensure_dirs()
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run("keyshift.api:app", host=config.HOST, port=config.PORT)

import sys
import os
import webbrowser
import threading
import time


def open_browser():
    time.sleep(3)
    webbrowser.open("http://localhost:8501")


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        # PyInstaller로 빌드된 exe 실행 시
        app_path = os.path.join(sys._MEIPASS, "app.py")
    else:
        app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")

    threading.Thread(target=open_browser, daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]

    from streamlit.web import cli as stcli
    sys.exit(stcli.main())

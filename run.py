"""شغّلني: يثبّت ما ينقص تلقائيًا، يشغّل الخادم، ويفتح المتصفح."""
import importlib.util, os, subprocess, sys, threading, time, webbrowser
ROOT = os.path.dirname(os.path.abspath(__file__)); os.chdir(ROOT); sys.path.insert(0, ROOT)
PORT = int(os.environ.get("PORT", "8000"))
NEED = {"fastapi": "fastapi", "uvicorn": "uvicorn", "multipart": "python-multipart", "PIL": "pillow", "numpy": "numpy",
        "httpx": "httpx", "reportlab": "reportlab", "arabic_reshaper": "arabic-reshaper", "bidi": "python-bidi"}
miss = [pkg for mod, pkg in NEED.items() if importlib.util.find_spec(mod) is None]
if miss:
    print("جاري تثبيت:", " ".join(miss))
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *miss])
import uvicorn
if os.environ.get("MAJHAR_NO_BROWSER") != "1":
    threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(f"http://127.0.0.1:{PORT}")), daemon=True).start()
uvicorn.run("app.main:app", host="127.0.0.1", port=PORT)

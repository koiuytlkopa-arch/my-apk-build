import os, threading
def start(files_dir):
    os.environ["MAJHAR_DB"] = os.path.join(files_dir, "majhar.db")
    import uvicorn
    from app.main import app
    cfg = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
    threading.Thread(target=uvicorn.Server(cfg).run, daemon=True).start()

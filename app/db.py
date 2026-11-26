"""SQLite: ذاكرة مؤقتة بحسب البصمة + سجل القضايا."""
import json, os, sqlite3, time

DB_PATH = os.environ.get("MAJHAR_DB", os.path.join(os.path.dirname(__file__), "..", "data", "majhar.db"))


def _conn():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("""CREATE TABLE IF NOT EXISTS results(
        key TEXT PRIMARY KEY, sha256 TEXT, filename TEXT, label TEXT, score REAL,
        created REAL, payload TEXT)""")
    return c


def get(key):
    c = _conn()
    try:
        r = c.execute("SELECT payload FROM results WHERE key=?", (key,)).fetchone()
    finally:
        c.close()
    return json.loads(r[0]) if r else None


def put(key, res):
    c = _conn()
    try:
        with c:
            c.execute("INSERT OR REPLACE INTO results VALUES(?,?,?,?,?,?,?)",
                      (key, res["sha256"], res["filename"], res["verdict"]["label"],
                       res["verdict"]["score"], time.time(), json.dumps(res, ensure_ascii=False)))
    finally:
        c.close()


def cases(limit=50):
    c = _conn()
    try:
        rows = c.execute("SELECT key,sha256,filename,label,score,created FROM results "
                         "ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    finally:
        c.close()
    return [dict(zip(("key", "sha256", "filename", "label", "score", "created"), r)) for r in rows]

import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["MAJHAR_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ.pop("GOOGLE_VISION_API_KEY", None); os.environ.pop("TINEYE_API_KEY", None)

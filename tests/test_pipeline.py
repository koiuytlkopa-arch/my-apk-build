import math
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app import pipeline, osint, judge, db, report
from app.main import app
from . import samples

client = TestClient(app)


def test_early_stop_on_generation_params():
    r = pipeline.analyze(samples.ai_png_with_params(), "a.png")
    assert r["verdict"]["label"] == "مولّدة غالباً" and r["verdict"]["decisive"]
    st = {s["id"]: s["status"] for s in r["stages"]}
    assert st["forensics"] == "skipped" and st["model"] == "skipped"
    assert r["ela_png"] is None


def test_real_camera_not_flagged_as_ai():
    r = pipeline.analyze(samples.photo_like(), "p.jpg")
    assert r["verdict"]["score"] < 50
    assert any(e["direction"] == "real" for e in r["evidence"])
    assert r["osint"]["gps"]["status"] == "ok" and r["osint"]["sun"]["status"] == "ok"
    assert r["osint"]["sun"]["daylight"] is True


def test_absence_of_evidence_stays_undecided():
    r = pipeline.analyze(samples.plain_png(), "x.png")
    assert r["verdict"]["label"] == "غير حاسم"
    assert not r["verdict"]["decisive"]


def test_never_scans_twice(monkeypatch):
    data = samples.photo_like(seed=9)
    calls = {"n": 0}
    orig = pipeline.metadata.analyze
    monkeypatch.setattr(pipeline.metadata, "analyze", lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1), orig(*a, **k))[1])
    a = pipeline.analyze(data, "p.jpg"); b = pipeline.analyze(data, "other-name.jpg")
    assert calls["n"] == 1 and b["cached"] is True and a["sha256"] == b["sha256"]


def test_works_without_api_keys_and_reports_what_failed():
    r = pipeline.analyze(samples.photo_like(seed=4), "p.jpg", allow_external=True, allow_upload=True)
    assert r["osint"]["reverse_search"]["status"] == "skipped"
    assert any("مفتاح" in l for l in r["limits"])
    assert "error" not in r


def test_corrupt_and_non_image():
    assert "error" in pipeline.analyze(b"not an image", "x.jpg")


def test_sun_position_equinox_noon_equator():
    s = osint.sun_position(0.0, 0.0, datetime(2024, 3, 20, 12, 7, tzinfo=timezone.utc))
    assert s["elevation"] > 85
    s2 = osint.sun_position(0.0, 0.0, datetime(2024, 3, 20, 0, 0, tzinfo=timezone.utc))
    assert s2["elevation"] < -60


def test_sun_azimuth_morning_is_east():
    s = osint.sun_position(30.0, 31.0, datetime(2024, 6, 21, 4, 0, tzinfo=timezone.utc))  # ~6 صباحاً شمسياً
    assert 45 < s["azimuth"] < 100 and s["elevation"] > 0


def test_judge_bands_and_caps():
    assert judge.label_for(90) == "مولّدة غالباً" and judge.label_for(5) == "حقيقية غالباً"
    ev = [{"stage": "metadata", "direction": "real", "weight": 30, "decisive": False}] * 3
    assert judge.judge(ev)["score"] >= 20


def test_reports_md_and_pdf():
    r = pipeline.analyze(samples.photo_like(seed=5), "p.jpg")
    blocks = report.build_blocks(r, notes="ملاحظة", checked=[report.CHECKLIST[0]])
    md = report.to_markdown(blocks)
    for must in ("حدود التقرير", "قائمة تحقق يدوية", r["sha256"], "ملاحظة", "[x]"):
        assert must in md
    pdf = report.to_pdf(blocks)
    assert pdf[:4] == b"%PDF" and len(pdf) > 3000


def test_api_batch_cases_and_report():
    files = [("files", ("a.jpg", samples.photo_like(seed=11), "image/jpeg")),
             ("files", ("b.png", samples.ai_png_with_params(), "image/png")),
             ("files", ("c.txt", b"hello", "text/plain"))]
    j = client.post("/api/analyze", files=files).json()["results"]
    assert len(j) == 3 and "error" in j[2] and j[1]["verdict"]["decisive"]
    assert len(client.get("/api/cases").json()["cases"]) >= 2
    rp = client.post(f"/api/report/md?key={j[0]['key']}", json={"notes": "n", "checked": []})
    assert rp.status_code == 200 and "حدود التقرير" in rp.text
    assert client.post(f"/api/report/pdf?key={j[0]['key']}", json={}).content[:4] == b"%PDF"
    assert client.get("/api/health").json()["ok"]

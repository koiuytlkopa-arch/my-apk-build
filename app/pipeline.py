"""خط المعالجة المتدرج مع الإيقاف المبكر والذاكرة المؤقتة."""
import hashlib, io, os, time
from datetime import datetime, timezone
from PIL import Image
from . import db, metadata, forensics, osint, detector, judge
from .common import ev, NEUTRAL

Image.MAX_IMAGE_PIXELS = 120_000_000
MAX_BYTES = 30 * 1024 * 1024
AMBIGUOUS = (35.0, 65.0)

FIXED_LIMITS = [
    "الدرجة تقديرية وغير مُعايَرة على بيانات حقيقية ما لم تُشغَّل tools/calibrate.py؛ ليست نسبة دقة ولا احتمالاً إحصائياً.",
    "غياب الأدلة لا يثبت الأصالة: البيانات الوصفية تُجرَّد أو تُزوَّر بسهولة، وضغط المنصات يطمس الآثار الجنائية.",
    "مؤشرات الضجيج وFFT وELA ضعيفة بطبيعتها وقد تُنتجها صور حقيقية مُعالَجة أو رسوم رقمية.",
    "وجود C2PA تُفحص فيه سلسلة المنشأ نصياً فقط؛ لم يُتحقق من التوقيع التشفيري للشهادات.",
    "لا يتعرف التقرير على الأشخاص بالوجوه ولا يبني ملفات عنهم؛ نطاقه الصورة وأصلها ومزاعمها فقط.",
    "موضع الشمس تقدير فلكي (±0.5° تقريباً) يعتمد على صحة الزمن والإحداثيات المسجَّلين، وهما قابلان للتعديل.",
]


def _timed(stages, sid, name, fn):
    t = time.perf_counter()
    out = fn()
    stages.append({"id": sid, "name": name, "status": "done", "ms": round((time.perf_counter() - t) * 1000, 1), "note": ""})
    return out


def _skip(stages, sid, name, note):
    stages.append({"id": sid, "name": name, "status": "skipped", "ms": 0, "note": note})


def cache_key(sha, allow_external, allow_upload):
    return f"{sha}:{int(allow_external)}{int(allow_upload)}"


def analyze(data: bytes, filename: str, allow_external=False, allow_upload=False):
    t0 = time.perf_counter()
    sha = hashlib.sha256(data).hexdigest()
    key = cache_key(sha, allow_external, allow_upload)
    cached = db.get(key)
    if cached:
        cached["cached"] = True
        return cached

    res = {"key": key, "sha256": sha, "filename": filename, "size": len(data), "cached": False,
           "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "options": {"allow_external": allow_external, "allow_upload": allow_upload}}
    stages, evidence, limits = [], [], list(FIXED_LIMITS)
    stages.append({"id": "fingerprint", "name": "البصمة والذاكرة المؤقتة", "status": "done", "ms": round((time.perf_counter() - t0) * 1000, 1),
                   "note": "صورة جديدة؛ لم تُفحص سابقاً بهذه الخيارات."})
    if len(data) > MAX_BYTES:
        return {**res, "error": f"الملف أكبر من {MAX_BYTES // 1048576} ميغابايت."}
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return {**res, "error": "الملف ليس صورة مقروءة أو أنه تالف."}
    res.update({"format": img.format, "width": img.size[0], "height": img.size[1]})

    # 2) البيانات الوصفية
    m_ev, m_info = _timed(stages, "metadata", "البيانات الوصفية والمنشأ", lambda: metadata.analyze(data, img))
    evidence += m_ev
    early = any(e["decisive"] for e in m_ev)

    # 3) التحليل الجنائي + 4) نموذج الكشف — يُتخطيان عند الحسم المبكر
    ela_png, f_metrics = None, {}
    if early:
        _skip(stages, "forensics", "التحليل الجنائي الخفيف", "إيقاف مبكر: دليل منشأ حاسم.")
        _skip(stages, "model", "نموذج الكشف المدرّب", "إيقاف مبكر: دليل منشأ حاسم.")
    else:
        f_ev, f_metrics, ela_png = _timed(stages, "forensics", "التحليل الجنائي الخفيف", lambda: forensics.analyze(img, img.format))
        evidence += f_ev
        interim = judge.judge(evidence)["score"]
        if AMBIGUOUS[0] <= interim <= AMBIGUOUS[1]:
            out = _timed(stages, "model", "نموذج الكشف المدرّب", lambda: detector.run(img))
            if out[0] is None:
                stages[-1].update(status="skipped", note=out[1])
                limits.append("مرحلة النموذج المدرّب لم تُنفَّذ: " + out[1])
            else:
                evidence += out[0]
        else:
            _skip(stages, "model", "نموذج الكشف المدرّب", f"إيقاف مبكر: الدرجة المبدئية {interim} خارج النطاق الغامض.")

    # 5) الاستقصاء — المحلي دائماً (رخيص)، والخارجي بموافقة
    def run_osint():
        loc, o_ev = osint.local_geo(m_info["exif"], m_info["gps"])
        ext, e_ev, lim = osint.external(data, m_info["gps"], m_info["exif"], allow_external, allow_upload)
        loc.update(ext)
        loc["manual_links"] = osint.manual_links(filename, sha)
        return loc, o_ev + e_ev, lim
    o, o_ev, o_lim = _timed(stages, "osint", "الاستقصاء (OSINT)", run_osint)
    evidence += o_ev
    limits += o_lim
    if not allow_external:
        limits.append("الاتصالات الخارجية معطّلة (لم تُمنح موافقة): لا عنوان من GPS ولا أقدم ظهور في الأرشيف.")

    # 6) الحكم
    verdict = _timed(stages, "judge", "وكيل الحكم", lambda: judge.judge(evidence))
    res.update({"stages": stages, "evidence": evidence, "metadata": m_info, "forensics": f_metrics,
                "osint": o, "ela_png": ela_png, "verdict": verdict, "limits": limits,
                "total_ms": round((time.perf_counter() - t0) * 1000, 1)})
    db.put(key, res)
    return res

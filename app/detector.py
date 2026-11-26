"""المرحلة 4: نموذج كشف مدرّب (ONNX) — اختياري ولا يُشغَّل إلا للحالات الغامضة.
ضع نموذجاً ثنائياً (مخرج واحد: احتمال التوليد) في MAJHAR_MODEL_PATH.
بدون النموذج أو onnxruntime تُعاد None ويُوضّح التقرير أن المرحلة لم تُنفَّذ."""
import os
from .common import ev, AI, REAL, NEUTRAL

ST = "model"


def available():
    p = os.environ.get("MAJHAR_MODEL_PATH")
    if not p or not os.path.exists(p):
        return False, "لا يوجد نموذج كشف: عيّن MAJHAR_MODEL_PATH إلى ملف ONNX."
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False, "onnxruntime غير مثبّت."
    return True, ""


def run(img):
    ok, why = available()
    if not ok:
        return None, why
    import numpy as np, onnxruntime as ort
    sess = ort.InferenceSession(os.environ["MAJHAR_MODEL_PATH"], providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    size = int(os.environ.get("MAJHAR_MODEL_SIZE", "224"))
    x = np.asarray(img.convert("RGB").resize((size, size)), dtype=np.float32) / 255.0
    x = np.transpose(x, (2, 0, 1))[None]
    p = float(np.ravel(sess.run(None, {inp.name: x})[0])[0])
    d = AI if p >= 0.5 else REAL
    w = int(min(60, abs(p - 0.5) * 120))
    return [ev(ST, "تقدير نموذج الكشف", f"احتمال التوليد الخام من النموذج = {p:.2f} (غير مُعايَر).", d, w)], ""

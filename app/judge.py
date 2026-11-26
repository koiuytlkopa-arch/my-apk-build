"""المرحلة 6: وكيل الحكم — يوازن الأدلة بجمع لوغاريتمي مع سقوف تحفظية.
الدرجة تقديرية وغير مُعايَرة؛ ليست احتمالاً إحصائياً."""
import math
from .common import AI, REAL

BANDS = [(85, "مولّدة غالباً"), (65, "تميل للتوليد"), (35, "غير حاسم"), (15, "تميل لكونها حقيقية"), (0, "حقيقية غالباً")]


def label_for(score):
    for lo, name in BANDS:
        if score >= lo:
            return name
    return BANDS[-1][1]


def judge(evidence):
    logit = 0.0
    for e in evidence:
        if e["direction"] == AI:
            logit += e["weight"] / 100 * 3.0
        elif e["direction"] == REAL:
            logit -= e["weight"] / 100 * 3.0
    score = 100 / (1 + math.exp(-logit))
    decisive = [e for e in evidence if e["decisive"] and e["direction"] == AI]
    notes = []
    if decisive:
        score = max(score, 93.0)
        notes.append("حُسم الحكم بدليل منشأ صريح (إقرار موجود داخل الملف). غياب مثل هذه الأدلة لا يثبت العكس.")
    else:
        strong = [e for e in evidence if e["weight"] >= 30]
        if not strong:
            # لا دليل قوي في أي اتجاه: الحكم لا يتجاوز نطاق «غير حاسم» (غياب الأدلة لا يثبت الأصالة)
            score = min(max(score, 36.0), 64.0)
            notes.append("لا يوجد دليل قوي في أي اتجاه، فبقي الحكم ضمن «غير حاسم».")
        else:
            # بيانات الأصالة الوصفية قابلة للتزوير: لا نهبط تحت 20 إلا بدليل مستقل من نموذج كشف مدرّب
            model_real = any(e["stage"] == "model" and e["direction"] == REAL and e["weight"] >= 40 for e in evidence)
            score = max(score, 8.0 if model_real else 20.0)
            if score == 20.0:
                notes.append("سُقّفت درجة الأصالة عند 20 لأن أدلتها مصدرها بيانات وصفية قابلة للتزوير.")
    score = round(score, 1)
    return {"score": score, "label": label_for(score), "decisive": bool(decisive), "notes": notes}

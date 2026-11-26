"""أدوات مشتركة: بناء الأدلة وتسمية الاتجاهات."""
AI, REAL, NEUTRAL = "ai", "real", "neutral"
DIR_AR = {AI: "تدعم التوليد", REAL: "تدعم الأصالة", NEUTRAL: "محايدة"}


def ev(stage, label, detail, direction=NEUTRAL, weight=0, decisive=False):
    """دليل واحد. weight من 0 إلى 100 (قوة الدليل لا احتماله)."""
    return {"stage": stage, "label": label, "detail": detail,
            "direction": direction, "weight": weight, "decisive": decisive}

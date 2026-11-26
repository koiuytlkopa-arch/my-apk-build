"""التقرير العربي: كتل منظمة تُصدَّر إلى Markdown وPDF."""
import io, os
from datetime import datetime, timezone
from .common import AI, REAL, NEUTRAL, DIR_AR

CHECKLIST = [
    "الظلال: اتجاهها وطولها متسقان مع موضع الشمس المحسوب وبين الأجسام المختلفة",
    "النصوص واللافتات: حروف مقروءة وصحيحة الإملاء وغير مشوّهة",
    "الأيدي والأصابع والأسنان والأذنان: عدد وتشريح طبيعيان",
    "الانعكاسات (زجاج/ماء/عيون/مرايا): تطابق المشهد المنعكس مع المصدر",
    "مطابقة الموقع: المعالم والمباني واللوحات تطابق المكان المزعوم (خرائط/Street View)",
    "الطقس والتاريخ: الغطاء النباتي والإضاءة والطقس يطابقون التاريخ المزعوم",
    "الاتساق: المنظور والمقياس والإضاءة موحّدة عبر الصورة، وحواف الأجسام نظيفة",
]
BANNER = {"مولّدة غالباً": "▰▰▰▰▰", "تميل للتوليد": "▰▰▰▰▱", "غير حاسم": "▰▰▰▱▱",
          "تميل لكونها حقيقية": "▰▰▱▱▱", "حقيقية غالباً": "▰▱▱▱▱"}


def _osint_blocks(o):
    b = []
    g = o.get("gps", {})
    if g.get("status") == "ok":
        b.append(("li", f"GPS: {g['lat']}, {g['lon']}" + (f" (ارتفاع {g['alt_m']} م)" if 'alt_m' in g else "")))
        b.append(("li", f"خريطة: {g['map_osm']}"))
    else:
        b.append(("li", f"GPS: {g.get('detail', 'غير متاح')}"))
    t = o.get("time", {})
    b.append(("li", f"الزمن (UTC): {t.get('utc') or '—'} — {t.get('detail', '')}"))
    s = o.get("sun")
    if s:
        b.append(("li", f"موضع الشمس: ارتفاع {s['elevation']}°، سمت {s['azimuth']}° ({s['sun_direction_ar']}). "
                        f"اتجاه الظلال المتوقع: {s['shadow_direction_ar']} ({s['shadow_direction']}°)"
                        + (f"، الطول ≈ {s['shadow_to_height']}× الارتفاع" if s.get("shadow_to_height") else "")))
    a = o.get("address", {})
    b.append(("li", "العنوان: " + (a.get("address") or a.get("detail") or "—")))
    r = o.get("reverse_search", {})
    if r.get("status") == "ok":
        gv = r.get("google_vision", {}); ti = r.get("tineye", {})
        n = len(gv.get("pages", [])) + len(gv.get("full_matches", [])) + len(ti.get("matches", []))
        b.append(("li", f"البحث العكسي: {n} مطابقة"))
        for p in gv.get("pages", [])[:8]:
            b.append(("li", f"  • {p.get('title') or ''} {p.get('url')}"))
        for m in ti.get("matches", [])[:8]:
            b.append(("li", f"  • {m.get('url')} (زحف: {m.get('crawl_date')})"))
    else:
        b.append(("li", "البحث العكسي: " + r.get("detail", "غير متاح")))
    e = o.get("earliest", {})
    b.append(("li", "أقدم ظهور: " + (e["first"][:10] if e.get("first") else (e.get("detail") or "—"))))
    b.append(("p", "روابط بحث يدوي مساعدة:"))
    for k, v in o.get("manual_links", {}).items():
        b.append(("li", f"{k}: {v}"))
    return b


def build_blocks(res, notes="", checked=None):
    checked = set(checked or [])
    if res.get("error"):
        return [("h1", "تقرير مجهر الصور"), ("p", f"الملف: {res.get('filename')}"), ("p", f"تعذّر الفحص: {res['error']}")]
    v = res["verdict"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    b = [("h1", "تقرير مجهر الصور"),
         ("li", f"اسم الملف: {res['filename']}  ({res.get('format')}، {res.get('width')}×{res.get('height')}، {res['size']:,} بايت)"),
         ("li", f"البصمة SHA-256: {res['sha256']}"),
         ("li", f"تاريخ التقرير: {now}  |  زمن الفحص الكلي: {res['total_ms']} ملّي ثانية" + ("  |  نتيجة مخزّنة" if res.get("cached") else "")),
         ("h2", "الحكم"),
         ("p", f"{v['label']} — درجة الميل نحو التوليد: {v['score']:.0f}/100   {BANNER.get(v['label'], '')}"),
         ("p", "المقياس: 0 حقيقية غالباً … 100 مولّدة غالباً. الدرجة تقديرية غير مُعايَرة.")]
    b += [("li", n) for n in v.get("notes", [])]
    b.append(("h2", "الأدلة حسب المرحلة"))
    names = {s["id"]: s for s in res["stages"]}
    order = [("metadata", "المرحلة 2: البيانات الوصفية والمنشأ"), ("forensics", "المرحلة 3: التحليل الجنائي الخفيف"),
             ("model", "المرحلة 4: نموذج الكشف"), ("osint", "المرحلة 5: الاستقصاء")]
    for sid, title in order:
        s = names.get(sid, {})
        status = "تم التخطي: " + s.get("note", "") if s.get("status") == "skipped" else f"{s.get('ms', 0)} ملّي ثانية"
        b.append(("h3", f"{title} — {status}"))
        items = [e for e in res["evidence"] if e["stage"] == sid]
        if not items:
            b.append(("li", "لا أدلة في هذه المرحلة."))
        for dirn in (AI, REAL, NEUTRAL):
            for e in [x for x in items if x["direction"] == dirn]:
                tag = f"[{DIR_AR[dirn]}" + (" — حاسم" if e["decisive"] else (f" — قوة {e['weight']}" if e["weight"] else "")) + "]"
                b.append(("li", f"{tag} {e['label']}: {e['detail']}"))
    b.append(("h2", "نتائج الاستقصاء (OSINT)"))
    b += _osint_blocks(res["osint"])
    b.append(("h2", "قائمة تحقق يدوية"))
    for c in CHECKLIST:
        b.append(("check", ("x" if c in checked else " ", c)))
    b.append(("h2", "ملاحظات المحلل"))
    b.append(("p", notes.strip() or "…………………………………………"))
    b.append(("h2", "حدود التقرير"))
    b += [("li", x) for x in res["limits"]]
    return b


def to_markdown(blocks):
    out = []
    for k, t in blocks:
        if k == "h1": out.append(f"# {t}\n")
        elif k == "h2": out.append(f"\n## {t}\n")
        elif k == "h3": out.append(f"\n### {t}\n")
        elif k == "li": out.append(f"- {t}")
        elif k == "check": out.append(f"- [{t[0]}] {t[1]}")
        else: out.append(f"\n{t}\n")
    return "\n".join(out) + "\n"


# ---------- PDF ----------
_FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_CANDIDATES = [os.environ.get("MAJHAR_FONT", ""), os.path.join(_FD, "DejaVuSans.ttf"), "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"]
BOLD_CANDIDATES = [os.environ.get("MAJHAR_FONT_BOLD", ""), os.path.join(_FD, "DejaVuSans-Bold.ttf"), "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]


def _first(paths):
    return next((p for p in paths if p and os.path.exists(p)), None)


def to_pdf(blocks):
    import arabic_reshaper
    try:
        from bidi import get_display          # python-bidi >= 0.5
    except ImportError:
        from bidi.algorithm import get_display  # python-bidi 0.4.x
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    reg, bold = _first(FONT_CANDIDATES), _first(BOLD_CANDIDATES) or _first(FONT_CANDIDATES)
    if not reg:
        raise RuntimeError("لا يوجد خط يدعم العربية؛ عيّن MAJHAR_FONT إلى ملف TTF.")
    pdfmetrics.registerFont(TTFont("R", reg)); pdfmetrics.registerFont(TTFont("B", bold))
    W, H = A4; M = 48
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("تقرير مجهر الصور")
    state = {"y": H - M}

    def vis(s):
        return get_display(arabic_reshaper.reshape(s))

    def wrap(text, font, size, maxw):
        lines, cur = [], ""
        for w in text.split(" "):
            cand = (cur + " " + w).strip()
            if pdfmetrics.stringWidth(vis(cand), font, size) <= maxw or not cur:
                cur = cand
            else:
                lines.append(cur); cur = w
        if cur:
            lines.append(cur)
        return lines

    def put(text, font="R", size=10.5, indent=0, gap=3, color=(0.1, 0.1, 0.12)):
        c.setFont(font, size)
        for ln in wrap(text, font, size, W - 2 * M - indent):
            if state["y"] < M + size:
                c.showPage(); state["y"] = H - M; c.setFont(font, size)
            c.setFillColorRGB(*color)
            c.drawRightString(W - M - indent, state["y"], vis(ln))
            state["y"] -= size * 1.5
        state["y"] -= gap

    for k, t in blocks:
        if k == "h1": put(t, "B", 20, gap=8, color=(0.05, 0.3, 0.3))
        elif k == "h2": state["y"] -= 6; put(t, "B", 14, gap=4, color=(0.05, 0.3, 0.3))
        elif k == "h3": put(t, "B", 11.5, gap=2)
        elif k == "li": put("• " + t, indent=8)
        elif k == "check": put(f"[{t[0]}] {t[1]}", indent=8)
        else: put(t)
    c.save()
    return buf.getvalue()

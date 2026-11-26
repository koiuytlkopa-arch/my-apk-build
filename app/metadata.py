"""المرحلة 2: البيانات الوصفية والمنشأ (EXIF / XMP / IPTC / C2PA / آثار أدوات التوليد)."""
import re
from .common import ev, AI, REAL, NEUTRAL

ST = "metadata"

# أسماء أدوات التوليد (تُفحص في الحقول النصية فقط، لا في البايتات الخام، لتجنّب الإيجابيات الكاذبة)
AI_TOOLS = {
    "midjourney": "Midjourney", "stable diffusion": "Stable Diffusion", "stablediffusion": "Stable Diffusion",
    "dall-e": "DALL·E", "dall·e": "DALL·E", "dalle": "DALL·E", "adobe firefly": "Adobe Firefly",
    "firefly": "Adobe Firefly", "comfyui": "ComfyUI", "automatic1111": "AUTOMATIC1111",
    "invokeai": "InvokeAI", "novelai": "NovelAI", "leonardo.ai": "Leonardo.Ai", "ideogram": "Ideogram",
    "synthid": "SynthID", "dreamstudio": "DreamStudio", "sdxl": "SDXL", "google imagen": "Google Imagen",
    "bing image creator": "Bing Image Creator", "runwayml": "Runway",
}
# معاملات التوليد (prompt/sampler...) الشائعة في وسوم PNG/EXIF/XMP
PARAM_PATTERNS = [
    r"negative prompt\s*:", r"\bsampler\s*[:=]", r"\bcfg[ _]scale\s*[:=]", r"\bsteps\s*:\s*\d+",
    r'"class_type"\s*:\s*"(?:ksampler|checkpointloader)', r"\bseed\s*[:=]\s*\d{5,}", r"--ar\s+\d+:\d+",
]
AI_SOURCE_TYPES = ("trainedalgorithmicmedia", "compositewithtrainedalgorithmicmedia", "algorithmicmedia")


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _gps_deg(vals, ref):
    d, m, s = (_f(x) for x in vals)
    if None in (d, m, s):
        return None
    out = d + m / 60 + s / 3600
    return -out if ref in ("S", "W") else out


def _ifd(ex, tag):
    try:
        return {int(k): v for k, v in ex.get_ifd(tag).items()}
    except Exception:
        return {}


def _dec(v):
    if isinstance(v, bytes):
        v = v.replace(b"ASCII\x00\x00\x00", b"")
        return v.decode("utf-8", "ignore").strip("\x00 ")
    return str(v).strip()


def analyze(data, img):
    evs, info, texts = [], {}, []

    # --- EXIF ---
    ex = img.getexif()
    base = {int(k): v for k, v in ex.items()}
    sub, gps = _ifd(ex, 0x8769), _ifd(ex, 0x8825)
    cam = {k: _dec(base[t]) for k, t in (("make", 271), ("model", 272), ("software", 305),
                                          ("artist", 315), ("description", 270)) if t in base}
    cam.update({k: _dec(sub[t]) for k, t in (("lens", 42036), ("datetime_original", 36867),
                                              ("offset_original", 36881), ("user_comment", 37510)) if t in sub})
    for k, t in (("exposure", 33434), ("f_number", 33437), ("iso", 34855), ("focal_length", 37386)):
        if t in sub:
            cam[k] = str(_f(sub[t]) if _f(sub[t]) is not None else sub[t])
    if "datetime_original" not in cam and 306 in base:
        cam["datetime"] = _dec(base[306])
    info["exif"] = cam
    texts += [cam.get(k, "") for k in ("software", "description", "user_comment", "artist", "make", "model")]

    # --- GPS ---
    g = None
    if 2 in gps and 4 in gps:
        lat = _gps_deg(gps[2], gps.get(1, "N"))
        lon = _gps_deg(gps[4], gps.get(3, "E"))
        if lat is not None and lon is not None:
            g = {"lat": round(lat, 6), "lon": round(lon, 6)}
            if 6 in gps and _f(gps[6]) is not None:
                g["alt_m"] = round(_f(gps[6]), 1)
            if 7 in gps and 29 in gps:
                h, m, s = (int(_f(x) or 0) for x in gps[7])
                g["utc"] = f"{_dec(gps[29]).replace(':', '-')}T{h:02d}:{m:02d}:{s:02d}+00:00"
    info["gps"] = g

    # --- نصوص PNG/XMP ---
    for k, v in (img.info or {}).items():
        if isinstance(v, (str, bytes)) and k not in ("icc_profile", "exif"):
            texts.append(f"{k}: {_dec(v)[:6000]}")
    m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", data, re.S)
    if m:
        texts.append(m.group(0).decode("utf-8", "ignore"))
    info["has_xmp"] = bool(m)
    blob = "\n".join(texts).lower()

    # --- C2PA / Content Credentials (وجود فقط؛ التوقيع لا يُتحقق منه) ---
    c2pa = b"c2pa" in data and b"jumb" in data
    info["c2pa_present"] = c2pa
    c2pa_txt = ""
    if c2pa:
        i = data.find(b"c2pa")
        c2pa_txt = data[max(0, i - 2000): i + 60000].decode("latin-1", "ignore").lower()
    scope = blob + "\n" + c2pa_txt

    # --- أدلة حاسمة ---
    if any(t in scope for t in AI_SOURCE_TYPES):
        evs.append(ev(ST, "وسم نوع المصدر الرقمي = وسائط مولّدة بالذكاء الاصطناعي",
                      "ورد DigitalSourceType بقيمة trainedAlgorithmicMedia/algorithmicMedia (IPTC/C2PA). "
                      "الوسم قابل للحذف أو التزوير، لكنه إقرار صريح من الأداة الصانعة.", AI, 97, True))
    elif "digitalcapture" in scope:
        evs.append(ev(ST, "وسم نوع المصدر = التقاط رقمي", "DigitalSourceType=digitalCapture؛ إقرار لم يُتحقق من توقيعه.", REAL, 15))

    tools = sorted({v for k, v in AI_TOOLS.items() if k in blob})
    if tools:
        evs.append(ev(ST, "ذُكرت أداة توليد في الحقول النصية", "الأدوات: " + "، ".join(tools), AI, 90, True))
    hits = [p for p in PARAM_PATTERNS if re.search(p, blob, re.I)]
    if len(hits) >= 2 or (hits and "prompt" in blob):
        evs.append(ev(ST, "معاملات توليد (prompt/sampler/steps) داخل الملف",
                      f"طُوبقت {len(hits)} أنماط من معاملات أدوات التوليد.", AI, 96, True))
    if c2pa:
        gen = sorted({v for k, v in AI_TOOLS.items() if k in c2pa_txt})
        if gen:
            evs.append(ev(ST, "مانيفست C2PA ينسب الصورة لأداة توليد", "الأدوات: " + "، ".join(gen), AI, 95, True))
        else:
            evs.append(ev(ST, "مانيفست C2PA موجود",
                          "وُجد Content Credentials؛ لم تُتحقق سلسلة الشهادات هنا ولا يظهر فيه ادعاء توليد.", REAL, 20))

    # --- بصمة الكاميرا ---
    cam_keys = [k for k in ("make", "model", "exposure", "f_number", "iso", "focal_length", "datetime_original") if k in cam]
    if len(cam_keys) >= 5:
        evs.append(ev(ST, "بيانات التقاط كاملة (جهاز/تعريض/ISO/بؤرة/وقت)",
                      (f"{cam.get('make', '')} {cam.get('model', '')}".strip() or "—") +
                      " — وجودها لا يثبت الأصالة لأنها قابلة للنسخ والتزوير.", REAL, 30))
    elif not cam_keys:
        evs.append(ev(ST, "لا توجد بيانات EXIF للكاميرا",
                      "كثير من المنصات تجرّد البيانات؛ الغياب لا يدل على التوليد ولا على الأصالة.", NEUTRAL, 0))
    else:
        evs.append(ev(ST, "بيانات EXIF جزئية", "الموجود: " + "، ".join(cam_keys), NEUTRAL, 0))
    if cam.get("software"):
        evs.append(ev(ST, "برنامج المعالجة المسجَّل", cam["software"], NEUTRAL, 0))

    # --- الأبعاد ---
    w, h = img.size
    if w % 64 == 0 and h % 64 == 0 and min(w, h) >= 256:
        evs.append(ev(ST, "الأبعاد من مضاعفات 64",
                      f"{w}×{h}: نمط شائع في مخرجات النماذج التوليدية، لكن الصور المقصوصة قد تطابقه صدفة.", AI, 14))
    return evs, info

"""المرحلة 3: تحليل جنائي خفيف على المعالج فقط.
كل العتبات هنا تقديرية وغير مُعايَرة ما لم تُشغَّل tools/calibrate.py على بيانات حقيقية."""
import base64, io
import numpy as np
from PIL import Image, ImageFilter
from .common import ev, AI, REAL, NEUTRAL

ST = "forensics"
THRESH = {"low_noise": 1.0, "noise_corr_real": 0.30, "fft_peaks_ai": 4, "fft_z": 6.0}


def _center_crop(a, n):
    h, w = a.shape
    n = min(n, h, w)
    y, x = (h - n) // 2, (w - n) // 2
    return a[y:y + n, x:x + n]


def noise_analysis(img):
    g = img.convert("L")
    blur = g.filter(ImageFilter.GaussianBlur(1.2))
    a = _center_crop(np.asarray(g, dtype=np.float32), 1024)
    b = _center_crop(np.asarray(blur, dtype=np.float32), 1024)
    res = a - b
    bs = 32
    H, W = (res.shape[0] // bs) * bs, (res.shape[1] // bs) * bs
    if H < bs * 2 or W < bs * 2:
        return None
    rb = res[:H, :W].reshape(H // bs, bs, W // bs, bs).swapaxes(1, 2).reshape(-1, bs * bs)
    lb = a[:H, :W].reshape(H // bs, bs, W // bs, bs).swapaxes(1, 2).reshape(-1, bs * bs).mean(1)
    sd = rb.std(1)
    ok = (lb > 12) & (lb < 243)
    if ok.sum() < 8:
        return None
    sd, lb = sd[ok], lb[ok]
    corr = float(np.corrcoef(lb, sd)[0, 1]) if sd.std() > 1e-6 and lb.std() > 1e-6 else 0.0
    return {"noise_median": float(np.median(sd)), "noise_cv": float(sd.std() / (sd.mean() + 1e-6)),
            "noise_luma_corr": corr, "blocks": int(ok.sum())}


def fft_analysis(img, is_jpeg):
    g = img.convert("L")
    a = _center_crop(np.asarray(g, dtype=np.float32), 512)
    n = a.shape[0]
    if n < 128:
        return None
    a = a[:n, :n]
    res = a - np.asarray(g.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32)[
        (g.size[1] - n) // 2:(g.size[1] - n) // 2 + n, (g.size[0] - n) // 2:(g.size[0] - n) // 2 + n]
    win = np.outer(np.hanning(n), np.hanning(n)).astype(np.float32)
    F = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(res * win))))
    yy, xx = np.indices(F.shape)
    c = n // 2
    r = np.hypot(yy - c, xx - c).astype(int)
    cnt = np.bincount(r.ravel())
    mean = np.bincount(r.ravel(), F.ravel()) / np.maximum(cnt, 1)
    var = np.bincount(r.ravel(), (F.ravel() - mean[r.ravel()]) ** 2) / np.maximum(cnt, 1)
    z = (F - mean[r]) / (np.sqrt(var[r]) + 1e-6)
    mask = (r > 8) & (r < c - 2) & (np.abs(yy - c) > 2) & (np.abs(xx - c) > 2)
    if is_jpeg:  # استبعاد ترددات شبكة JPEG 8×8
        step = n // 8
        near = ((np.abs((yy - c) % step) <= 2) | (np.abs((yy - c) % step) >= step - 2)) & \
               ((np.abs((xx - c) % step) <= 2) | (np.abs((xx - c) % step) >= step - 2))
        mask &= ~near
    zz = np.where(mask, z, 0)
    peaks = int((zz > THRESH["fft_z"]).sum())
    return {"fft_peaks": peaks, "fft_max_z": float(zz.max())}


def ela(img, is_jpeg, q=90):
    rgb = img.convert("RGB")
    rgb.thumbnail((1024, 1024))
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=q)
    buf.seek(0)
    re_img = Image.open(buf).convert("RGB")
    d = np.abs(np.asarray(rgb, dtype=np.int16) - np.asarray(re_img, dtype=np.int16)).max(2).astype(np.float32)
    mx = float(d.max()) or 1.0
    vis = Image.fromarray(np.clip(d * (255.0 / mx), 0, 255).astype(np.uint8)).convert("L")
    vis.thumbnail((480, 480))
    out = io.BytesIO()
    vis.save(out, "PNG", optimize=True)
    return {"ela_mean": float(d.mean()), "ela_std": float(d.std()), "ela_max": mx}, base64.b64encode(out.getvalue()).decode()


def analyze(img, fmt):
    evs, metrics = [], {}
    is_jpeg = (fmt or "").upper() in ("JPEG", "JPG")
    n = noise_analysis(img)
    if n:
        metrics.update(n)
        flat = n["noise_median"] < THRESH["low_noise"] and n["noise_cv"] < 0.6
        if flat:
            evs.append(ev(ST, "ضجيج حسّي منخفض وموحّد على نحو غير معتاد",
                          f"وسيط الضجيج {n['noise_median']:.2f} ومعامل التباين {n['noise_cv']:.2f}. "
                          "قد ينتج أيضاً عن إزالة ضجيج أو ضغط شديد أو رسوم رقمية.", AI, 14))
        elif n["noise_luma_corr"] > THRESH["noise_corr_real"]:
            evs.append(ev(ST, "الضجيج يرتفع مع السطوع كما في المستشعرات الفعلية",
                          f"ارتباط الضجيج بالسطوع = {n['noise_luma_corr']:.2f} (سلوك شوت-نويز). "
                          "قد يحاكيه التوليد أو يخفيه الضغط.", REAL, 12))
        else:
            evs.append(ev(ST, "تحليل الضجيج", f"وسيط {n['noise_median']:.2f}، ارتباط بالسطوع {n['noise_luma_corr']:.2f} — لا إشارة واضحة.", NEUTRAL, 0))
    else:
        evs.append(ev(ST, "تحليل الضجيج تعذّر", "الصورة صغيرة جداً أو مشبعة بالكامل.", NEUTRAL, 0))

    f = fft_analysis(img, is_jpeg)
    if f:
        metrics.update(f)
        if f["fft_peaks"] >= THRESH["fft_peaks_ai"]:
            evs.append(ev(ST, "قمم دورية في طيف التردد (FFT)",
                          f"{f['fft_peaks']} قمة عند z>{THRESH['fft_z']:.0f} (أقصاها {f['fft_max_z']:.1f}). "
                          "نمط مرتبط بالرفع (upsampling) في بعض النماذج، وقد تسببه أيضاً الأنماط الدورية أو إعادة التحجيم.", AI, 22))
        else:
            evs.append(ev(ST, "طيف FFT بلا قمم دورية لافتة", f"{f['fft_peaks']} قمة فقط.", NEUTRAL, 0))

    m, ela_png = ela(img, is_jpeg)
    metrics.update(m)
    evs.append(ev(ST, "خريطة ELA للفحص البصري",
                  "الخريطة مرفقة للمحلل: المناطق الأفتح بكثافة مختلفة قد تدل على معالجة موضعية. "
                  + ("" if is_jpeg else "الصورة غير JPEG فتفسير ELA هنا محدود جداً."), NEUTRAL, 0))
    return evs, metrics, ela_png

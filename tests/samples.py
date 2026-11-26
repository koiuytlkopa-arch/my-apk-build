"""مولّد عيّنات اصطناعية للاختبار. عيّنات حقيقية/مولّدة فعلية تُوضع في tools/calibrate.py."""
import io
import numpy as np
from PIL import Image, PngImagePlugin


def photo_like(w=1000, h=750, seed=1, exif=True, gps=True):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    base = 60 + 120 * (x / w) * 0.6 + 60 * (y / h)
    lum = np.clip(base, 10, 240)
    noise = rng.normal(0, 1, (h, w)) * (1.5 + lum / 40)       # ضجيج يزداد مع السطوع
    arr = np.clip(lum + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([arr, arr * 0.95, arr * 0.9]).astype(np.uint8))
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[271], ex[272], ex[305] = "Canon", "EOS R6", "Firmware 1.8"
        sub = {33434: 0.005, 33437: 2.8, 34855: 200, 37386: 35.0, 36867: "2024:06:21 12:00:00", 36881: "+02:00"}
        ex[0x8769] = sub
        if gps:
            ex[0x8825] = {1: "N", 2: (48.0, 51.0, 24.0), 3: "E", 4: (2.0, 17.0, 40.0)}
        img.save(buf, "JPEG", quality=92, exif=ex)
    else:
        img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def ai_png_with_params(w=1024, h=1024):
    y, x = np.mgrid[0:h, 0:w]
    arr = (128 + 100 * np.sin(x / 90) * np.cos(y / 70)).astype(np.uint8)
    img = Image.fromarray(np.dstack([arr, arr, arr]))
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", "a castle at dusk\nNegative prompt: blurry\nSteps: 28, Sampler: Euler a, CFG scale: 7, Seed: 1234567")
    buf = io.BytesIO(); img.save(buf, "PNG", pnginfo=info)
    return buf.getvalue()


def plain_png(w=700, h=500, seed=3):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    buf = io.BytesIO(); Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()

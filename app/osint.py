"""المرحلة 5: الاستقصاء.
- المحلي دائماً: تحويل GPS، توحيد الزمن، موضع الشمس واتجاه الظلال، روابط بحث يدوي.
- الخارجي فقط بموافقة صريحة: Nominatim (إحداثيات فقط)، أرشيف الإنترنت CDX (روابط فقط)،
  Google Vision/TinEye (يرفعان الصورة نفسها، ويتطلبان allow_upload ومفتاحاً).
كل خدمة تتدهور بمرونة: تُسجَّل حالتها (ok/skipped/failed) وسببها ولا تُسقط الفحص."""
import base64, math, os, urllib.parse
from datetime import datetime, timedelta, timezone
import httpx
from .common import ev, AI, REAL, NEUTRAL

ST = "osint"
UA = "MajharAlSowar/1.0 (image-verification tool)"
TIMEOUT = float(os.environ.get("MAJHAR_HTTP_TIMEOUT", "8"))


def sun_position(lat, lon, dt_utc):
    """موضع الشمس (ارتفاع وسمت من الشمال باتجاه الشرق) بخوارزمية فلكية مبسّطة (±~0.5°)."""
    jd = dt_utc.timestamp() / 86400 + 2440587.5
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 4e-7 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    ha = math.radians((gmst * 15 + lon) % 360) - ra
    la = math.radians(lat)
    el = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(math.sin(ha), math.cos(ha) * math.sin(la) - math.tan(dec) * math.cos(la))
    return {"elevation": round(math.degrees(el), 1), "azimuth": round((math.degrees(az) + 180) % 360, 1)}


def _compass(deg):
    names = ["شمال", "شمال شرق", "شرق", "جنوب شرق", "جنوب", "جنوب غرب", "غرب", "شمال غرب"]
    return names[int((deg + 22.5) // 45) % 8]


def resolve_time(exif, gps):
    """يعيد (UTC datetime, وصف دقة الزمن). الأفضل: ختم GPS الزمني، ثم EXIF مع الإزاحة، ثم تقدير من خط الطول."""
    if gps and gps.get("utc"):
        return datetime.fromisoformat(gps["utc"]), "ختم GPS الزمني (UTC) — الأدق"
    raw = exif.get("datetime_original") or exif.get("datetime")
    if not raw:
        return None, "لا يوجد زمن في الملف"
    try:
        local = datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None, f"صيغة زمن غير مفهومة: {raw}"
    off = exif.get("offset_original")
    if off and len(off) >= 6 and off[0] in "+-":
        sign = 1 if off[0] == "+" else -1
        delta = timedelta(hours=int(off[1:3]), minutes=int(off[4:6])) * sign
        return (local - delta).replace(tzinfo=timezone.utc), f"زمن EXIF محلي مع إزاحة {off}"
    if gps:
        est = round(gps["lon"] / 15)
        return (local - timedelta(hours=est)).replace(tzinfo=timezone.utc), \
            f"زمن EXIF محلي بلا إزاحة؛ قُدّرت المنطقة الزمنية UTC{est:+d} من خط الطول (تقديري)"
    return None, "زمن EXIF محلي ولا توجد إحداثيات لتقدير المنطقة الزمنية"


def local_geo(exif, gps):
    out, evs = {}, []
    if not gps:
        out["gps"] = {"status": "skipped", "detail": "لا توجد إحداثيات GPS في الملف."}
        return out, evs
    lat, lon = gps["lat"], gps["lon"]
    out["gps"] = {"status": "ok", **gps,
                  "map_osm": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}",
                  "map_google": f"https://www.google.com/maps?q={lat},{lon}"}
    evs.append(ev(ST, "إحداثيات GPS مضمّنة", f"{lat}, {lon}. وجودها لا يثبت أن الصورة التُقطت هناك فعلاً (قابلة للتعديل).", NEUTRAL, 0))
    t, how = resolve_time(exif, gps)
    out["time"] = {"status": "ok" if t else "skipped", "detail": how, "utc": t.isoformat() if t else None}
    if t:
        s = sun_position(lat, lon, t)
        shadow = (s["azimuth"] + 180) % 360
        sun = {"status": "ok", **s, "sun_direction_ar": _compass(s["azimuth"]),
               "shadow_direction": round(shadow, 1), "shadow_direction_ar": _compass(shadow),
               "shadow_to_height": round(1 / math.tan(math.radians(s["elevation"])), 2) if s["elevation"] > 2 else None,
               "daylight": s["elevation"] > 0}
        out["sun"] = sun
        evs.append(ev(ST, "موضع الشمس المحسوب لموقع الصورة وزمنها",
                      f"الارتفاع {s['elevation']}° والسمت {s['azimuth']}° ({sun['sun_direction_ar']}). "
                      f"يُتوقع أن تمتد الظلال نحو {sun['shadow_direction_ar']}"
                      + (f" بطول ≈ {sun['shadow_to_height']}× ارتفاع الجسم." if sun["shadow_to_height"] else
                         ("؛ الشمس شبه ملامسة للأفق." if sun["daylight"] else "؛ الشمس تحت الأفق (ليل/غسق)."))
                      + f" دقة الزمن: {how}. قارن يدوياً مع الظلال في الصورة.", NEUTRAL, 0))
    return out, evs


def manual_links(filename, sha):
    q = urllib.parse.quote
    links = {
        "Google Lens (رفع يدوي)": "https://lens.google.com/",
        "TinEye (رفع يدوي)": "https://tineye.com/",
        "Yandex Images (رفع يدوي)": "https://yandex.com/images/",
        "Bing Visual Search (رفع يدوي)": "https://www.bing.com/visualsearch",
        "بحث باسم الملف": f"https://www.google.com/search?q={q(chr(34) + filename + chr(34))}",
        "بحث بالبصمة SHA-256": f"https://www.google.com/search?q={sha}",
    }
    return links


def reverse_geocode(lat, lon):
    r = httpx.get("https://nominatim.openstreetmap.org/reverse", timeout=TIMEOUT, headers={"User-Agent": UA},
                  params={"lat": lat, "lon": lon, "format": "jsonv2", "accept-language": "ar", "zoom": 18})
    r.raise_for_status()
    j = r.json()
    return {"address": j.get("display_name"), "parts": j.get("address", {})}


def google_vision(data, key):
    body = {"requests": [{"image": {"content": base64.b64encode(data).decode()},
                          "features": [{"type": "WEB_DETECTION", "maxResults": 15}]}]}
    r = httpx.post(f"https://vision.googleapis.com/v1/images:annotate?key={key}", json=body, timeout=TIMEOUT * 3)
    r.raise_for_status()
    w = (r.json().get("responses") or [{}])[0].get("webDetection", {})
    return {
        "pages": [{"url": p.get("url"), "title": p.get("pageTitle")} for p in w.get("pagesWithMatchingImages", [])],
        "full_matches": [x.get("url") for x in w.get("fullMatchingImages", [])],
        "partial_matches": [x.get("url") for x in w.get("partialMatchingImages", [])],
        "entities": [e.get("description") for e in w.get("webEntities", []) if e.get("description")][:10],
    }


def tineye(data, key):
    """تكامل TinEye — لم يُختبر ضد الخدمة الحية لعدم توفر مفتاح أثناء البناء؛ راجع وثائق TinEye قبل الاعتماد."""
    r = httpx.post("https://api.tineye.com/rest/search/", params={"api_key": key},
                   files={"image_upload": ("image", data)}, timeout=TIMEOUT * 3)
    r.raise_for_status()
    ms = (r.json().get("results") or {}).get("matches", [])
    return {"matches": [{"url": (m.get("backlinks") or [{}])[0].get("url"), "crawl_date": (m.get("backlinks") or [{}])[0].get("crawl_date"),
                         "image_url": m.get("image_url")} for m in ms[:15]]}


def wayback_first(url):
    r = httpx.get("https://web.archive.org/cdx/search/cdx", timeout=TIMEOUT, headers={"User-Agent": UA},
                  params={"url": url, "output": "json", "fl": "timestamp,original", "filter": "statuscode:200", "limit": 1})
    r.raise_for_status()
    rows = r.json()
    if len(rows) > 1:
        ts = rows[1][0]
        return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return None


def external(data, gps, exif, allow_external, allow_upload):
    """يعيد (osint dict, evidence list, limits list)."""
    out, evs, limits = {}, [], []

    # Nominatim: إحداثيات فقط، لا تُرسل الصورة
    if gps and allow_external:
        try:
            out["address"] = {"status": "ok", **reverse_geocode(gps["lat"], gps["lon"])}
            evs.append(ev(ST, "العنوان المقابل للإحداثيات (Nominatim)", out["address"]["address"] or "—", NEUTRAL, 0))
        except Exception as e:
            out["address"] = {"status": "failed", "detail": f"{type(e).__name__}"}
            limits.append("تعذّر تحويل GPS إلى عنوان (Nominatim): الخدمة غير متاحة أو لا يوجد اتصال.")
    elif gps:
        out["address"] = {"status": "skipped", "detail": "لم تُمنح موافقة على الاتصالات الخارجية."}
    else:
        out["address"] = {"status": "skipped", "detail": "لا توجد إحداثيات."}

    # البحث العكسي: يرفع الصورة، موافقة صريحة + مفتاح
    gv, ti = os.environ.get("GOOGLE_VISION_API_KEY"), os.environ.get("TINEYE_API_KEY")
    matches_urls, rev = [], {}
    if not allow_upload:
        rev["status"] = "skipped"
        rev["detail"] = "البحث العكسي يرفع الصورة لجهة خارجية ولم تُمنح موافقة صريحة على الرفع."
    elif not (gv or ti):
        rev["status"] = "skipped"
        rev["detail"] = "لا يوجد مفتاح GOOGLE_VISION_API_KEY أو TINEYE_API_KEY."
        limits.append("البحث العكسي لم يُنفَّذ: لا يوجد مفتاح API. استخدم الروابط اليدوية أدناه.")
    else:
        rev["status"] = "ok"
        if gv:
            try:
                rev["google_vision"] = google_vision(data, gv)
                matches_urls += rev["google_vision"]["full_matches"] + [p["url"] for p in rev["google_vision"]["pages"]]
            except Exception as e:
                rev["google_vision"] = {"status": "failed", "detail": type(e).__name__}
                limits.append("فشل البحث عبر Google Vision.")
        if ti:
            try:
                rev["tineye"] = tineye(data, ti)
                matches_urls += [m["url"] for m in rev["tineye"]["matches"] if m.get("url")]
            except Exception as e:
                rev["tineye"] = {"status": "failed", "detail": type(e).__name__}
                limits.append("فشل البحث عبر TinEye.")
        n = len(matches_urls)
        evs.append(ev(ST, "مطابقات البحث العكسي", f"عُثر على {n} رابطاً مطابقاً أو مشابهاً." if n else
                      "لم تُعثر مطابقات؛ هذا لا يعني أن الصورة جديدة.", NEUTRAL, 0))
    out["reverse_search"] = rev

    # أقدم ظهور: أرشيف الإنترنت للروابط المطابقة (الروابط فقط تُرسل)
    if matches_urls and allow_external:
        first, seen = None, []
        for u in list(dict.fromkeys(matches_urls))[:8]:
            try:
                t = wayback_first(u)
                if t:
                    seen.append({"url": u, "first_archived": t.isoformat()})
                    first = t if (first is None or t < first) else first
            except Exception:
                continue
        out["earliest"] = {"status": "ok" if seen else "skipped", "items": seen,
                           "first": first.isoformat() if first else None,
                           "detail": None if seen else "لا توجد لقطات أرشيفية للروابط المطابقة."}
        if first:
            exif_dt = exif.get("datetime_original")
            note = ""
            try:
                if exif_dt and datetime.strptime(exif_dt[:19], "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc) > first + timedelta(days=1):
                    note = " تنبيه: زمن EXIF أحدث من أقدم ظهور موثّق — تعارض يستدعي التدقيق."
                    evs.append(ev(ST, "تعارض زمني: EXIF أحدث من أقدم ظهور", note.strip(), AI, 20))
            except ValueError:
                pass
            evs.append(ev(ST, "أقدم ظهور موثّق في الأرشيف", f"{first.date()} (أقدم لقطة أرشيفية لصفحة مطابقة؛ ليست بالضرورة أول نشر).{note}", NEUTRAL, 0))
    else:
        out["earliest"] = {"status": "skipped", "detail": "لا روابط مطابقة أو لا موافقة خارجية."}
    return out, evs, limits

"""معايرة عتبات التحليل الجنائي على عيّنات حقيقية ومولّدة.
الاستعمال:  python tools/calibrate.py --real مجلد_صور_حقيقية --ai مجلد_صور_مولّدة
يستخرج مقاييس الضجيج وFFT وELA بلا أي اتصال خارجي، ثم يبحث عن أفضل عتبة لكل مقياس
(أعلى دقة متوازنة) ويطبع جدولاً + AUC تقريبية. انقل العتبات المقترحة إلى THRESH في app/forensics.py.
مهم: هذه الأداة لا تأتي معها صور؛ ضع عيّناتك أنت (يفضّل مئات الصور من مصادر ومنصات ضغط متنوعة)."""
import argparse, glob, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import forensics

METRICS = ["noise_median", "noise_cv", "noise_luma_corr", "fft_peaks", "fft_max_z", "ela_mean", "ela_std"]


def collect(folder):
    rows = []
    for p in glob.glob(os.path.join(folder, "**", "*"), recursive=True):
        try:
            img = Image.open(p); img.load()
            m = {}
            m.update(forensics.noise_analysis(img) or {})
            m.update(forensics.fft_analysis(img, (img.format or "").upper() == "JPEG") or {})
            m.update(forensics.ela(img, False)[0])
            rows.append(m)
        except Exception as e:
            print("تخطّي", p, type(e).__name__)
    return rows


def auc(pos, neg):
    s = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return s / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--real", required=True); ap.add_argument("--ai", required=True)
    a = ap.parse_args()
    R, A = collect(a.real), collect(a.ai)
    print(f"عيّنات حقيقية: {len(R)} | مولّدة: {len(A)}\n")
    if len(R) < 20 or len(A) < 20:
        print("تحذير: أقل من 20 عيّنة لكل فئة؛ النتائج غير موثوقة إحصائياً.\n")
    print(f"{'المقياس':<18}{'AUC':>7}{'العتبة':>10}{'الدقة':>8}{'الاتجاه':>14}")
    for k in METRICS:
        r = [x[k] for x in R if k in x]; g = [x[k] for x in A if k in x]
        if not r or not g:
            continue
        au = auc(g, r)
        best = (0, None, None)
        for t in np.unique(np.concatenate([r, g])):
            for sign in (1, -1):
                acc = (np.mean([(v * sign) > (t * sign) for v in g]) + np.mean([(v * sign) <= (t * sign) for v in r])) / 2
                if acc > best[0]:
                    best = (acc, t, sign)
        print(f"{k:<18}{au:>7.2f}{best[1]:>10.3f}{best[0]:>8.2f}{'أعلى=توليد' if best[2] == 1 else 'أدنى=توليد':>14}")
    print("\nAUC≈0.5 تعني أن المقياس لا يفرّق؛ لا تعتمد مقياساً أقل من ~0.65.")


if __name__ == "__main__":
    main()

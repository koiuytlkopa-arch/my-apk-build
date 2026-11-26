# مجهر الصور

فحص جنائي رقمي للصور: هل هي مولّدة بالذكاء الاصطناعي؟ ما منشؤها وأقدم ظهور لها؟ تقرير عربي موثّق (Markdown/PDF).

## التشغيل
    pip install -r requirements.txt
    uvicorn app.main:app --port 8000        # ثم افتح http://localhost:8000
    # أو:  docker build -t majhar . && docker run -p 8000:8000 -v $PWD/data:/srv/data majhar

## المتغيرات الاختيارية (كلها اختيارية؛ الأداة تعمل بدونها وتوضح ما تعذّر)
- `GOOGLE_VISION_API_KEY` / `TINEYE_API_KEY`: البحث العكسي (يرفع الصورة، ويحتاج موافقة صريحة في الواجهة).
- `MAJHAR_MODEL_PATH`: نموذج كشف ONNX للحالات الغامضة (يحتاج onnxruntime).
- `MAJHAR_DB`, `MAJHAR_CONCURRENCY`, `MAJHAR_HTTP_TIMEOUT`, `MAJHAR_FONT`.

## الاختبارات والمعايرة
    python -m pytest -q tests
    python tools/calibrate.py --real صور_حقيقية/ --ai صور_مولّدة/

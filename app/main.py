"""واجهة FastAPI: فحص دفعات بالتوازي، تقارير، سجل القضايا."""
import asyncio, os
from typing import List
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import db, pipeline, report

app = FastAPI(title="مجهر الصور", version="1.0")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SEM = asyncio.Semaphore(int(os.environ.get("MAJHAR_CONCURRENCY", "4")))
MAX_FILES = 40


@app.post("/api/analyze")
async def analyze(files: List[UploadFile] = File(...), allow_external: bool = Form(False), allow_upload: bool = Form(False)):
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"الحد الأقصى {MAX_FILES} صورة في الدفعة.")
    blobs = [(f.filename or "image", await f.read()) for f in files]

    async def one(name, data):
        async with SEM:
            try:
                return await asyncio.wait_for(asyncio.to_thread(pipeline.analyze, data, name, allow_external, allow_upload), timeout=120)
            except asyncio.TimeoutError:
                return {"filename": name, "error": "انتهت مهلة الفحص (120 ثانية).", "sha256": ""}
            except Exception as e:  # لا نُسقط الدفعة بسبب ملف واحد
                return {"filename": name, "error": f"خطأ غير متوقع: {type(e).__name__}", "sha256": ""}
    return {"results": await asyncio.gather(*(one(n, d) for n, d in blobs))}


class ReportReq(BaseModel):
    notes: str = ""
    checked: List[str] = []


@app.post("/api/report/{fmt}")
def make_report(fmt: str, key: str, req: ReportReq):
    res = db.get(key)
    if not res:
        raise HTTPException(404, "لا توجد نتيجة بهذا المفتاح؛ أعد الفحص.")
    blocks = report.build_blocks(res, req.notes, req.checked)
    name = "majhar-report-" + res["sha256"][:12]
    if fmt == "md":
        return Response(report.to_markdown(blocks), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}.md"'})
    if fmt == "pdf":
        return Response(report.to_pdf(blocks), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})
    raise HTTPException(400, "الصيغة md أو pdf فقط.")


@app.get("/api/cases")
def cases():
    return {"cases": db.cases()}


@app.get("/api/health")
def health():
    from . import detector
    ok, why = detector.available()
    return {"ok": True, "model": ok, "model_note": why,
            "google_vision": bool(os.environ.get("GOOGLE_VISION_API_KEY")), "tineye": bool(os.environ.get("TINEYE_API_KEY"))}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")

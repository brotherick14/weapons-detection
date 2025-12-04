from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os
import cv2
import threading
import time

from detector.video_detector import process_video_file
from detector.live_detector import process_rtsp_stream
from detector.model_provider import get_model

app = FastAPI()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALERT_DIR = "alerts"
os.makedirs(ALERT_DIR, exist_ok=True)
STATIC_DIR = "static"
os.makedirs(STATIC_DIR, exist_ok=True)

stream_stop_event = threading.Event()
detection_stop_event = threading.Event()

# Servir imágenes de alertas como archivos estáticos
app.mount("/alerts", StaticFiles(directory=ALERT_DIR), name="alerts")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# -------------------------
# UI
# -------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -------------------------
# DETECCIÓN POR VIDEO FILE
# -------------------------
def process_video_and_cleanup(path: str, cleanup_delay: int = 60):
    """
    Ejecuta la detección sobre un archivo y lo elimina después de un retardo,
    para no acumular uploads en disco mientras se permite el streaming temporal.
    """
    try:
        process_video_file(path)
    finally:
        # Dar tiempo a que el stream use el archivo, luego eliminarlo
        time.sleep(cleanup_delay)
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"[CLEANUP] Upload eliminado: {path}")
            except OSError:
                pass


@app.post("/detect/video")
async def detect_video(file: UploadFile = File(...)):
    file_ext = file.filename.split(".")[-1]
    saved_name = f"{uuid.uuid4()}.{file_ext}"
    temp_name = f"{UPLOAD_DIR}/{saved_name}"

    with open(temp_name, "wb") as f:
        f.write(await file.read())

    # Procesar en segundo plano para ir generando alertas mientras se puede ver el stream
    threading.Thread(target=process_video_and_cleanup, args=(temp_name,), daemon=True).start()

    return JSONResponse({
        "file": saved_name,
        "original_filename": file.filename,
        "stream_url": f"/stream/video?file={saved_name}",
    })


# -------------------------
# STREAM DE VIDEO SUBIDO
# -------------------------
def generate_video_stream(path):
    model = get_model()
    stream_stop_event.clear()
    cap = cv2.VideoCapture(path)

    while not stream_stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, conf=0.4, iou=0.4)
        annotated = results[0].plot()

        ret, jpeg = cv2.imencode(".jpg", annotated)
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"

    cap.release()


@app.get("/stream/video")
def stream_video(file: str):
    path = f"{UPLOAD_DIR}/{file}"
    return StreamingResponse(
        generate_video_stream(path),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# -------------------------
# ALERTAS RECIENTES (leer carpeta)
# -------------------------
@app.get("/api/alerts/recent")
def recent_alerts(limit: int = 10):
    files = [f for f in os.listdir(ALERT_DIR) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(ALERT_DIR, f)), reverse=True)

    result = []
    for f in files[:limit]:
        ts = os.path.getmtime(os.path.join(ALERT_DIR, f))
        result.append({
            "image": f"/alerts/{f}",
            "timestamp": ts,
        })
    return result


# -------------------------
# DETECCIÓN POR RTSP
# -------------------------
@app.post("/detect/rtsp")
def detect_rtsp(rtsp_url: str = Form(...)):
    detection_stop_event.clear()
    threading.Thread(target=process_rtsp_stream, args=(rtsp_url, detection_stop_event), daemon=True).start()
    return JSONResponse({"status": "streaming started", "rtsp": rtsp_url})


# -------------------------
# DETECCIÓN POR WEBCAM
# -------------------------
@app.post("/detect/webcam")
def detect_webcam():
    detection_stop_event.clear()
    threading.Thread(target=process_rtsp_stream, args=(0, detection_stop_event), daemon=True).start()
    return JSONResponse({"status": "webcam detection started"})


# -------------------------
# STREAM PARA WEBCAM
# -------------------------
def generate_webcam_stream():
    model = get_model()
    stream_stop_event.clear()
    cap = cv2.VideoCapture(0)

    while not stream_stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            continue

        results = model(frame, conf=0.4)
        annotated = results[0].plot()

        ret, jpeg = cv2.imencode(".jpg", annotated)
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"

    cap.release()


@app.get("/stream")
def webcam_stream():
    return StreamingResponse(
        generate_webcam_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# -------------------------
# STREAM PARA RTSP
# -------------------------
def generate_rtsp_stream(url):
    model = get_model()
    stream_stop_event.clear()
    cap = cv2.VideoCapture(url)

    while not stream_stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            continue

        results = model(frame, conf=0.4)
        annotated = results[0].plot()

        ret, jpeg = cv2.imencode(".jpg", annotated)
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"

    cap.release()


@app.get("/stream/rtsp")
def rtsp_stream(url: str):
    return StreamingResponse(
        generate_rtsp_stream(url),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# -------------------------
# STOP STREAM
# -------------------------
@app.post("/stream/stop")
def stop_stream():
    stream_stop_event.set()
    detection_stop_event.set()
    return {"status": "stopped"}

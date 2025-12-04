"""Detección en streams (webcam/RTSP) con YOLO y alertas a Telegram."""

import cv2
import time
import os
import threading
from typing import Optional
from alerts import send_telegram_alert
from detector.model_provider import get_model

ALERT_FOLDER = "alerts"
os.makedirs(ALERT_FOLDER, exist_ok=True)

CONF_SOFT = 0.40
CONF_HARD = 0.60
IOU_NMS = 0.40
MIN_AREA = 1500
MIN_RATIO = 1.1
FRAME_STREAK_REQUIRED = 2
ALERT_COOLDOWN = 5


def process_rtsp_stream(source, stop_event: Optional[threading.Event] = None):
    """
    Lee un stream (RTSP/webcam), corre YOLO en cada frame y envía alertas
    cuando se cumplen las condiciones configuradas. Puede detenerse con
    stop_event (señal externa) para liberar la cámara.
    """
    stop_event = stop_event or threading.Event()
    model = get_model()
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        return {"error": f"No se pudo abrir stream: {source}"}

    frame_streak = 0
    last_alert_time = 0
    last_box = None
    stable_hits = 0

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue

        results = model(frame, conf=CONF_SOFT, iou=IOU_NMS, verbose=False)

        # FRAME ANOTADO
        annotated = results[0].plot()

        gun_detected = False
        hard_hit = False
        best_conf = 0
        best_box = None

        for box in results[0].boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            if cls != 0:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w, h = x2 - x1, y2 - y1
            area = w * h
            ratio = w / h

            if area < MIN_AREA or ratio < MIN_RATIO:
                continue

            gun_detected = True
            if conf >= CONF_HARD:
                hard_hit = True

            if conf > best_conf:
                best_conf = conf
                best_box = (x1, y1, x2, y2)

        # -------- ESTABILIDAD --------
        if gun_detected and best_box:
            if last_box:
                lx1, ly1, lx2, ly2 = last_box
                bx1, by1, bx2, by2 = best_box

                dx = abs(bx1 - lx1) + abs(bx2 - lx2)
                dy = abs(by1 - ly1) + abs(by2 - ly2)

                if dx + dy < 200:
                    stable_hits += 1
                else:
                    stable_hits = 0

            last_box = best_box
        else:
            stable_hits = 0
            last_box = None

        frame_streak = frame_streak + 1 if gun_detected else 0
        now = time.time()

        if (
            frame_streak >= FRAME_STREAK_REQUIRED
            and hard_hit
            and stable_hits >= 1
            and (now - last_alert_time) > ALERT_COOLDOWN
        ):
            last_alert_time = now
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            img_path = f"{ALERT_FOLDER}/alert_{int(now)}.jpg"

            # GUARDAR ANOTADO
            cv2.imwrite(img_path, annotated)

            send_telegram_alert(
                message=f"⚠️ ARMA DETECTADA\nConfianza: {best_conf:.2f}\nFecha: {timestamp}",
                photo_path=img_path,
            )

    cap.release()
    return {"status": "stream ended"}

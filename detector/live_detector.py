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

# IoU usado para NMS (Non-Maximum Suppression)
# IoU = área_intersección / área_union
IOU_NMS = 0.40

# Filtro geométrico: armas reales deben ocupar cierto tamaño mínimo
MIN_AREA = 1500

# Filtro geométrico: las armas suelen ser alargadas
# relación = ancho / alto > 1.1
MIN_RATIO = 1.1

# Número de frames consecutivos donde el objeto debe detectarse
FRAME_STREAK_REQUIRED = 2

# Tiempo mínimo entre alertas (segundos)
ALERT_COOLDOWN = 10


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

    frame_streak = 0         # Cuenta cuántos frames consecutivos detectan arma
    last_alert_time = 0      # Para cooldown temporal
    last_box = None          # Box del frame anterior para estabilidad geométrica
    stable_hits = 0          # Conteo de estabilidad temporal del bounding box

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue

        # conf = CONF_SOFT, se activan detecciones preliminares
        results = model(frame, conf=CONF_SOFT, iou=IOU_NMS, verbose=False)

        # FRAME ANOTADO
        annotated = results[0].plot()

        # Flags de detección
        gun_detected = False
        hard_hit = False  # Se activa si conf >= CONF_HARD
        best_conf = 0
        best_box = None

        for box in results[0].boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            if cls != 0:
                continue

            # Extraer coordenadas de la caja
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w, h = x2 - x1, y2 - y1

            # Área de la caja → área = w * h
            area = w * h

            # Proporción geométrica → ratio = w / h
            ratio = w / h

            # -----------------------------
            #  HEURÍSTICAS DE FILTRADO
            # -----------------------------
            # Fórmulas aplicadas y justificación
            #
            # 1. Área mínima:
            #    área = w*h ≥ MIN_AREA
            #
            # 2. Proporción mínima:
            #    ratio = w/h ≥ MIN_RATIO
            #
            # Estas heurísticas eliminan:
            # - objetos demasiado pequeños,
            # - objetos cuadrados (celulares, cajas),
            # - detecciones falsas pequeñas.
            if area < MIN_AREA or ratio < MIN_RATIO:
                continue

            # Marca que se detectó arma en este frame
            gun_detected = True

            # Confirma detección si supera CONF_HARD
            if conf >= CONF_HARD:
                hard_hit = True

            # Guardar la mejor detección (mayor confianza)
            if conf > best_conf:
                best_conf = conf
                best_box = (x1, y1, x2, y2)

        # -----------------------------
        #     ESTABILIDAD DEL OBJETO
        # -----------------------------
        #
        # Lógica:
        # Queremos que la caja detectada
        #     sea consistente en frames consecutivos.
        #
        # Fórmula aplicada:
        # 
        # dx = |x1 - x1_prev| + |x2 - x2_prev|
        # dy = |y1 - y1_prev| + |y2 - y2_prev|
        #
        # Si dx + dy < UMBRAL → el objeto se considera estable
        #
        # Esto es equivalente a un filtro de coherencia temporal, evita ruido.
        if gun_detected and best_box:
            if last_box:
                lx1, ly1, lx2, ly2 = last_box
                bx1, by1, bx2, by2 = best_box

                dx = abs(bx1 - lx1) + abs(bx2 - lx2)
                dy = abs(by1 - ly1) + abs(by2 - ly2)

                # Umbral empírico: 200 px
                if dx + dy < 200:
                    stable_hits += 1
                else:
                    stable_hits = 0

            last_box = best_box
        else:
            # Si ya no hay detección, reiniciamos estabilidad
            stable_hits = 0
            last_box = None

        # Conteo de detecciones seguidas
        frame_streak = frame_streak + 1 if gun_detected else 0
        now = time.time()

        # -----------------------------
        #       CONDICIÓN DE ALERTA
        # -----------------------------
        #
        # Una alerta se envía si:
        #
        # 1) frame_streak ≥ FRAME_STREAK_REQUIRED
        # 2) hard_hit == True
        # 3) stable_hits ≥ 1
        # 4) cooldown cumplido → (now - last_alert_time) > ALERT_COOLDOWN
        #
        # Esta combinación:
        # - reduce falsos positivos,
        # - obliga a ver una detección persistente,
        # - exige confianza alta del modelo,
        # - impone estabilidad geométrica del bounding box.
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

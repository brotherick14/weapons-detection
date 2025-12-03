import cv2
import time
import os
import argparse
from ultralytics import YOLO
from alerts import send_telegram_alert

# -----------------------
# PARSE ARGS
# -----------------------
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=str, default="0", help="0=webcam, file path, etc.")
parser.add_argument("--rtsp", type=str, help="URL RTSP para cámara IP / seguridad")
parser.add_argument("--conf", type=float, default=0.40, help="Confianza mínima suave")
parser.add_argument("--retry", type=int, default=5, help="Reintentos al reconectar la cámara")
parser.add_argument("--retry-wait", type=float, default=2.0, help="Tiempo entre reintentos (s)")
args = parser.parse_args()

source_arg = args.rtsp or args.source
source = int(source_arg) if source_arg.isdigit() else source_arg
CONF_SOFT = args.conf
CONF_HARD = 0.60
IOU_NMS = 0.40
MIN_AREA = 2500
MIN_RATIO = 1.5
FRAME_STREAK_REQUIRED = 5
ALERT_COOLDOWN = 5

MODEL_PATH = "best.pt"
SAVE_ALERT_IMAGES = True
ALERT_FOLDER = "alerts"
os.makedirs(ALERT_FOLDER, exist_ok=True)


# -----------------------
# CARGAR MODELO
# -----------------------
model = YOLO(MODEL_PATH)
print(f"[INFO] Modelo cargado: {MODEL_PATH}")


# -----------------------
# VIDEO
# -----------------------
def open_capture(src):
    cap_local = cv2.VideoCapture(src)
    if not cap_local.isOpened():
        return None
    return cap_local


cap = open_capture(source)
if not cap:
    print(f"[ERROR] No se pudo abrir la fuente {source}")
    exit()

print(f"[INFO] Detección iniciada desde {source}. Presiona 'q' para salir.")

frame_streak = 0
last_alert_time = 0
last_box = None
stable_hits = 0

# -----------------------
# LOOP PRINCIPAL
# -----------------------
while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] Frame no recibido. Intentando reconectar...")
        cap.release()
        cap = None
        for attempt in range(1, args.retry + 1):
            time.sleep(args.retry_wait)
            cap = open_capture(source)
            if cap:
                print(f"[INFO] Reconectado en intento {attempt}")
                break
            print(f"[WARN] Reintento {attempt}/{args.retry} fallido")
        if not cap:
            print("[ERROR] No se pudo reconectar la cámara. Saliendo.")
            break
        continue

    results = model(frame, conf=CONF_SOFT, iou=IOU_NMS, verbose=False)
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

        if area < MIN_AREA:
            continue
        if ratio < MIN_RATIO:
            continue

        gun_detected = True
        if conf >= CONF_HARD:
            hard_hit = True

        if conf > best_conf:
            best_conf = conf
            best_box = (x1, y1, x2, y2)

    # -------------------
    # ESTABILIDAD (PAPER)
    # -------------------
    if gun_detected and best_box:
        if last_box:
            lx1, ly1, lx2, ly2 = last_box
            bx1, by1, bx2, by2 = best_box

            dx = abs(bx1 - lx1) + abs(bx2 - lx2)
            dy = abs(by1 - ly1) + abs(by2 - ly2)

            if dx + dy < 60:
                stable_hits += 1
            else:
                stable_hits = 0
        last_box = best_box
    else:
        stable_hits = 0
        last_box = None

    # -------------------
    # STREAK
    # -------------------
    if gun_detected:
        frame_streak += 1
    else:
        frame_streak = 0

    now = time.time()

    # -------------------
    # ALERTA FINAL
    # -------------------
    if (
        frame_streak >= FRAME_STREAK_REQUIRED
        and hard_hit
        and stable_hits >= 2
        and (now - last_alert_time > ALERT_COOLDOWN)
    ):
        last_alert_time = now
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        print(f"[ALERTA] ARMA DETECTADA — conf={best_conf:.2f} — {timestamp}")

        # Guardar imagen + enviar a Telegram
        image_path = None
        if SAVE_ALERT_IMAGES:
            image_path = f"{ALERT_FOLDER}/alert_{int(now)}.jpg"
            cv2.imwrite(image_path, frame)
            print(f"[INFO] Imagen guardada: {image_path}")

        send_telegram_alert(
            message=f"⚠️ ARMA DETECTADA\nConfianza: {best_conf:.2f}\nFecha: {timestamp}",
            photo_path=image_path,
        )

    cv2.imshow("Gun Detection - Live", annotated)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print("[INFO] Detección finalizada.")

# Gun Detection Demo

Panel web con FastAPI/Ultralytics YOLOv8 para detección de armas en video subido, webcam o RTSP, con alertas a Telegram y carrusel de imágenes. Incluye un script CLI (`local_testing.py`) para probar sin UI.
<img width="1461" height="782" alt="image" src="https://github.com/user-attachments/assets/0fc232fc-1211-44e5-b7b9-19947a73f353" />

## Requisitos
- Python 3.10+
- ffmpeg (recomendado para buen soporte de video)
- Dependencias: `pip install -r requirements.txt`

## Variables de entorno
Crear `.env` con:
```
TELEGRAM_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_chat_id
```
Opcionales:
```
MODEL_PATH=models/guns.pt                  # ruta al modelo YOLO (p.ej. models/knifes.pt)
```
Puedes tomar como base el `.env.example`

## Uso rápido sin UI (CLI)
`local_testing.py` ejecuta detección en bucle mostrando la ventana de OpenCV:
```
python local_testing.py --source 0             # webcam
python local_testing.py --source video1.mov    # archivo local
python local_testing.py --rtsp rtsp://user:pass@ip/stream
```
Teclas: `q` para salir. Envía alertas a Telegram si hay `.env`.

## Uso completo (con UI)
1) Instala dependencias: `pip install -r requirements.txt`
2) Corre el backend: `uvicorn api:app --reload`
3) Abre `http://127.0.0.1:8000`
   - La documentación interactiva de la API está en `http://127.0.0.1:8000/docs` (Swagger/Redoc) y puedes probar las rutas ahí mismo.
4) Sube un video o usa webcam/RTSP. Las detecciones guardan imágenes en `alerts/` y se muestran en el carrusel; se envía alerta a Telegram si está configurado.

Limpieza: los videos subidos se guardan temporalmente en `uploads/` y se borran después de procesar (delay corto). Las imágenes de alerta quedan en `alerts/`.

## Endpoints principales (api.py)
- `POST /detect/video` → sube video, empieza procesamiento en segundo plano, devuelve `stream_url`.
- `GET /stream/video?file=<uuid.ext>` → stream MJPEG anotado del video subido.
- `POST /detect/webcam` → inicia detección de webcam en background.
- `POST /detect/rtsp` (form `rtsp_url`) → inicia detección RTSP en background.
- `GET /stream` → stream MJPEG anotado de webcam.
- `GET /stream/rtsp?url=<rtsp>` → stream MJPEG anotado RTSP.
- `POST /stream/stop` → detiene streams y captura/detección en background.
- `GET /api/alerts/recent` → últimas imágenes en `alerts/`.

## Parámetros de detección (ajustables)
Se usan en ambos detectores (`detector/video_detector.py` y `detector/live_detector.py`):
- `CONF_SOFT` (0.40): confianza mínima para considerar un arma.
- `CONF_HARD` (0.60): confianza alta para disparar alerta.
- `IOU_NMS` (0.40): IOU para NMS.
- `MIN_AREA` (p.ej. 1500/2500): área mínima del bounding box.
- `MIN_RATIO` (p.ej. 1.1/1.5): relación ancho/alto mínima.
- `FRAME_STREAK_REQUIRED` (p.ej. 2/5): frames consecutivos que mantienen detección.
- `ALERT_COOLDOWN` (5s): tiempo mínimo entre alertas.

Puedes editar estos valores directamente en los archivos y reiniciar. El modelo se carga una sola vez (en `detector/model_provider.py`) usando `MODEL_PATH` o `models/guns.pt` por defecto.

## Arquitectura y decisiones técnicas
- **Carga única de modelo**: `detector/model_provider.py` expone `get_model()` con caché para reutilizar el modelo YOLO en API, detección en video y live, evitando cargas múltiples.
- **Procesamiento en background**: `api.py` lanza hilos para detección de videos (`process_video_and_cleanup`) y streams (webcam/RTSP) para que la UI responda rápido. Los videos se auto-eliminan tras un breve delay; las alertas se guardan en `alerts/`.
- **Separación de capas**: la lógica de detección está en `detector/`, la UI en `templates/` + `static/`, y las alertas en `alerts.py`. Los assets (favicon, CSS, JS) viven en `static/`.
- **Streaming MJPEG**: los endpoints `/stream*` generan frames anotados on-the-fly; `/stream/stop` corta tanto el stream como la captura/detección para liberar cámara.
- **Resultados de entrenamiento**: en `models/results/` se guardan gráficas y artefactos (train batch, test images) por modelo entrenado.

## Notas
- `uploads/` se crea en el proceso para procesar videos subidos; se limpia automáticamente después de procesar.
- `alerts/` almacena las imágenes de las alertas; sirve estático en `/alerts/…`.
- El favicon usa `static/button.png`; estilos en `static/styles.css`; JS en `static/app.js` (toda la lógica de la UI).
- En `models/results/` encuentras gráficas y pruebas de entrenamiento (train batch, test images) para cada modelo entrenado.

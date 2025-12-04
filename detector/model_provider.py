import os
from functools import lru_cache
from ultralytics import YOLO


@lru_cache(maxsize=1)
def get_model():
    """
    Carga el modelo YOLO una sola vez y lo reutiliza.
    Usa MODEL_PATH del entorno o models/guns.pt por defecto.
    """
    model_path = os.getenv("MODEL_PATH", "models/guns.pt")
    return YOLO(model_path)

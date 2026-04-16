# media/video_codec.py
import cv2
import numpy as np

JPEG_QUALITY = 50   # 0–100; menor = mais rápido, menor qualidade


def encode_frame(frame: np.ndarray) -> bytes:
    """Converte frame BGR do OpenCV para bytes JPEG."""
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise RuntimeError("Falha ao codificar frame")
    return buf.tobytes()


def decode_frame(data: bytes) -> np.ndarray:
    """Converte bytes JPEG de volta para frame BGR."""
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("Falha ao decodificar frame")
    return frame
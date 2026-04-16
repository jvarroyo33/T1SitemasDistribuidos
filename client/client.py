# client/capture.py
import threading
import queue
import time
import logging
import numpy as np

log = logging.getLogger(__name__)

# Importação condicional do pyaudio (pode não ter microfone no ambiente)
try:
    import pyaudio
    AUDIO_OK = True
except ImportError:
    AUDIO_OK = False
    log.warning("[CAPTURE] pyaudio não disponível — áudio desativado")

try:
    import cv2
    VIDEO_OK = True
except ImportError:
    VIDEO_OK = False
    log.warning("[CAPTURE] opencv não disponível — vídeo desativado")

from media.audio_codec import RATE, CHANNELS, CHUNK
from media.video_codec import encode_frame


class CaptureManager:
    """
    Gerencia captura de câmera e microfone em threads separadas.
    Produz frames/audio em filas para o Sender consumir.
    """

    def __init__(self, video_queue: queue.Queue, audio_queue: queue.Queue):
        self.video_q   = video_queue
        self.audio_q   = audio_queue
        self._running  = False
        self._threads  = []

    # ------------------------------------------------------------------
    # Vídeo
    # ------------------------------------------------------------------
    def _capture_video(self):
        if not VIDEO_OK:
            return
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            log.error("[CAPTURE] Câmera não encontrada")
            return
        log.info("[CAPTURE] Câmera iniciada")
        while self._running:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            try:
                data = encode_frame(frame)
                # Descarta frame antigo se fila cheia (QoS: drop)
                if self.video_q.full():
                    self.video_q.get_nowait()
                self.video_q.put_nowait(data)
            except Exception as e:
                log.error(f"[CAPTURE] Erro vídeo: {e}")
        cap.release()
        log.info("[CAPTURE] Câmera encerrada")

    # ------------------------------------------------------------------
    # Áudio
    # ------------------------------------------------------------------
    def _capture_audio(self):
        if not AUDIO_OK:
            return
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        log.info("[CAPTURE] Microfone iniciado")
        while self._running:
            try:
                pcm = stream.read(CHUNK, exception_on_overflow=False)
                if self.audio_q.full():
                    self.audio_q.get_nowait()
                self.audio_q.put_nowait(pcm)
            except Exception as e:
                log.error(f"[CAPTURE] Erro áudio: {e}")
        stream.stop_stream()
        stream.close()
        pa.terminate()
        log.info("[CAPTURE] Microfone encerrado")

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------
    def start(self):
        self._running = True
        tv = threading.Thread(target=self._capture_video, daemon=True, name="capture-video")
        ta = threading.Thread(target=self._capture_audio, daemon=True, name="capture-audio")
        self._threads = [tv, ta]
        for t in self._threads:
            t.start()

    def stop(self):
        self._running = False
        log.info("[CAPTURE] Captura encerrada")
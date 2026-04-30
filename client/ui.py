# client/ui.py
import cv2
import logging
import threading
import queue

log = logging.getLogger(__name__)

class UI:
    def __init__(self, capture_manager=None):
        self.video_q = queue.Queue(maxsize=10)
        self._running = False
        self.capture = capture_manager
        self.win_name = "Videoconferência"

    def display_video(self, frame):
        try:
            if self.video_q.full():
                self.video_q.get_nowait()
            self.video_q.put_nowait(frame)
        except: pass

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and self.capture:
            # Botão Mute (Esquerda)
            if 10 < x < 110 and 10 < y < 50:
                self.capture.audio_enabled = not self.capture.audio_enabled
                log.info(f"[UI] Audio: {'LIGADO' if self.capture.audio_enabled else 'MUTADO'}")
            
            # Botão Camera (Direita)
            if 120 < x < 220 and 10 < y < 50:
                self.capture.video_enabled = not self.capture.video_enabled
                log.info(f"[UI] Video: {'LIGADO' if self.capture.video_enabled else 'DESLIGADO'}")

    def _draw_controls(self, frame):
        if not self.capture: return
        
        # Fundo dos botões
        cv2.rectangle(frame, (5, 5), (230, 55), (50, 50, 50), -1)
        
        # Botão Audio
        a_col = (0, 255, 0) if self.capture.audio_enabled else (0, 0, 255)
        a_txt = "MUTE" if self.capture.audio_enabled else "UNMUTE"
        cv2.rectangle(frame, (10, 10), (110, 50), a_col, 2)
        cv2.putText(frame, a_txt, (25, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Botão Video
        v_col = (0, 255, 0) if self.capture.video_enabled else (0, 0, 255)
        v_txt = "CAM ON" if self.capture.video_enabled else "CAM OFF"
        cv2.rectangle(frame, (120, 10), (220, 50), v_col, 2)
        cv2.putText(frame, v_txt, (135, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def _render_loop(self):
        log.info("[UI] Renderizador de vídeo iniciado")
        cv2.namedWindow(self.win_name)
        cv2.setMouseCallback(self.win_name, self._on_mouse)
        
        while self._running:
            try:
                frame = self.video_q.get(timeout=0.05)
                self._draw_controls(frame)
                cv2.imshow(self.win_name, frame)
            except queue.Empty:
                pass
            except Exception as e:
                log.error(f"[UI] Erro render: {e}")
                break
                
            # OpenCV EXIGE que o waitKey seja chamado para não dar "Não responde"
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cv2.destroyAllWindows()

    def start(self):
        self._running = True
        self._render_loop()

    def stop(self):
        self._running = False

    def prompt(self, text):
        return input(text)

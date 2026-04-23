# client/ui.py
import cv2
import logging
import threading
import queue

log = logging.getLogger(__name__)

class UI:
    def __init__(self):
        self.video_q = queue.Queue(maxsize=10)
        self._running = False

    def display_video(self, frame):
        try:
            if self.video_q.full():
                self.video_q.get_nowait()
            self.video_q.put_nowait(frame)
        except: pass

    def _render_loop(self):
        log.info("[UI] Renderizador de vídeo iniciado")
        while self._running:
            try:
                frame = self.video_q.get(timeout=1)
                cv2.imshow("Videoconferência", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"[UI] Erro render: {e}")
                break
        cv2.destroyAllWindows()

    def start(self):
        self._running = True
        # OpenCV precisa rodar na thread principal em alguns sistemas, 
        # mas aqui vamos tentar em thread separada ou apenas gerenciar chamadas.
        threading.Thread(target=self._render_loop, daemon=True).start()

    def stop(self):
        self._running = False

    def prompt(self, text):
        return input(text)

import logging
import threading
import time
import queue
import sys
import os
import argparse

# Adiciona o diretório raiz ao path para importações
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from identity.session import Session
from capture import CaptureManager
from sender import Sender
from receiver import Receiver
from ui import UI
from media.video_codec import decode_frame
from media.audio_codec import RATE, CHANNELS, CHUNK

# Configuração de log
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

try:
    import pyaudio
    AUDIO_OK = True
except ImportError:
    AUDIO_OK = False

class VideoConferenceClient:
    def __init__(self, nome, sala, use_camera=True):
        self.session = Session(nome, sala, on_reconnect=self._on_broker_reconnect)
        self.use_camera = use_camera
        
        self.video_send_q = queue.Queue(maxsize=10)
        self.audio_send_q = queue.Queue(maxsize=50)
        
        self.capture = CaptureManager(self.video_send_q, self.audio_send_q)
        self.ui = UI(capture_manager=self.capture)
        self.sender = None
        self.receiver = None
        
        self.running = False
        
        # Audio Playback
        if AUDIO_OK:
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK
            )
        else:
            self.audio_stream = None

    def on_video_received(self, data):
        try:
            frame = decode_frame(data)
            self.ui.display_video(frame)
        except Exception as e:
            log.error(f"Erro decod vídeo: {e}")

    def on_audio_received(self, data):
        if self.audio_stream:
            try:
                self.audio_stream.write(data)
            except Exception as e:
                log.error(f"Erro audio playback: {e}")

    def on_text_received(self, text):
        print(f"\n[CHAT] {text}")
        print("Mensagem: ", end="", flush=True)

    def _send_loop(self):
        while self.running:
            if not self.session.online or not self.sender:
                time.sleep(0.1)
                continue
            
            # Prioridade Texto (verificado no input da main)
            
            # Vídeo
            try:
                while not self.video_send_q.empty():
                    data = self.video_send_q.get_nowait()
                    self.sender.send_video(data)
            except: pass
            
            # Áudio
            try:
                while not self.audio_send_q.empty():
                    data = self.audio_send_q.get_nowait()
                    self.sender.send_audio(data)
            except: pass
            
            time.sleep(0.01)

    def start(self):
        if not self.session.login():
            log.error("Falha inicial de login. Encerrando.")
            return

        self.running = True
        self.sender = Sender(self.session.context, self.session.broker_info)
        self.receiver = Receiver(self.session.context, self.session.broker_info,
                                 self.on_video_received, self.on_audio_received, self.on_text_received)
        
        self.receiver.start()
        
        if self.use_camera:
            self.capture.start()
        else:
            log.info("[CLIENTE] Modo sem câmera ativado — vídeo NÃO será capturado")
        
        self.ui.start()
        
        threading.Thread(target=self._send_loop, daemon=True).start()
        
        log.info("Cliente iniciado com sucesso!")
        
        # Loop de chat no terminal
        try:
            while self.running:
                msg = input("Mensagem (ou '/sair'): ")
                if msg == "/sair":
                    break
                if self.sender:
                    self.sender.send_text(msg, self.session.user_id)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def _on_broker_reconnect(self, new_broker_info):
        """Chamado pela Session quando o failover ocorre. Recria sockets no novo broker."""
        log.info("[CLIENTE] Recriando sockets de mídia no novo broker...")
        # Para os sockets antigos sem matar as threads de captura
        if self.sender:
            self.sender.stop()
        if self.receiver:
            self.receiver.stop()
        # Pequena pausa para os sockets ZMQ fecharem
        import time as _time
        _time.sleep(0.5)
        # Recria com o novo broker, mantendo a sala original
        self.sender = Sender(self.session.context, new_broker_info)
        self.receiver = Receiver(
            self.session.context, new_broker_info,
            self.on_video_received, self.on_audio_received, self.on_text_received
        )
        self.receiver.start()
        log.info(f"[CLIENTE] Sockets recriados. Sala '{self.session.sala}' mantida!")

    def stop(self):
        self.running = False
        if self.use_camera:
            self.capture.stop()
        if self.sender: self.sender.stop()
        if self.receiver: self.receiver.stop()
        self.ui.stop()
        self.session.logout()
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.pa.terminate()
        log.info("Cliente encerrado.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente de Videoconferência")
    parser.add_argument("--no-camera", action="store_true", dest="no_camera",
                        help="Inicia sem capturar vídeo da webcam")
    parser.add_argument("--nome", type=str, default=None,
                        help="Seu nome de exibição")
    parser.add_argument("--sala", type=str, default=None,
                        help="Sala (A-K)")
    args = parser.parse_args()
    
    nome = args.nome or input("Seu nome: ") or "User"
    sala = (args.sala or input("Sala (A-K): ") or "A").upper()
    
    client = VideoConferenceClient(nome, sala, use_camera=not args.no_camera)
    client.start()


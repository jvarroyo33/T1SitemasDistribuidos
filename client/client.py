# client/client.py
import logging
import threading
import time
import queue
import sys
import os

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
    def __init__(self, nome, sala):
        self.session = Session(nome, sala)
        self.ui = UI()
        
        self.video_send_q = queue.Queue(maxsize=10)
        self.audio_send_q = queue.Queue(maxsize=50)
        
        self.capture = CaptureManager(self.video_send_q, self.audio_send_q)
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
        self.capture.start()
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

    def stop(self):
        self.running = False
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
    nome = input("Seu nome: ") or "User"
    sala = input("Sala (A-K): ").upper() or "A"
    
    client = VideoConferenceClient(nome, sala)
    client.start()
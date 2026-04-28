# client/sender.py
import zmq
import logging
import queue
import threading
import time

log = logging.getLogger(__name__)

class Sender:
    def __init__(self, context, broker_info):
        self.context = context
        self.broker_info = broker_info
        self.host = "localhost" # Simplificação
        
        self.v_sock = self.context.socket(zmq.PUB)
        self.v_sock.connect(f"tcp://{self.host}:{broker_info['ports']['video_in']}")
        
        self.a_sock = self.context.socket(zmq.PUB)
        self.a_sock.connect(f"tcp://{self.host}:{broker_info['ports']['audio_in']}")
        
        self.t_sock = self.context.socket(zmq.PUB)
        self.t_sock.connect(f"tcp://{self.host}:{broker_info['ports']['text_in']}")
        
        self.running = False
        self.sala = broker_info.get("sala", "A")

    def send_video(self, data):
        # Tópico: sala
        self.v_sock.send_multipart([self.sala.encode(), data])

    def send_audio(self, data):
        self.a_sock.send_multipart([self.sala.encode(), data])

    def send_text(self, text, user_id):
        msg = f"{user_id}: {text}"
        # QoS: Retry poderia ser implementado aqui se tivéssemos um canal de ACK
        # Por enquanto, enviamos via PUB no tópico da sala
        self.t_sock.send_multipart([self.sala.encode(), msg.encode()])
        log.info(f"Texto enviado: {text}")

    def stop(self):
        self.running = False
        self.v_sock.close()
        self.a_sock.close()
        self.t_sock.close()

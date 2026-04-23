# broker/broker.py
import zmq
import threading
import logging
import signal
import sys
import time
import uuid
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BROKER-%(broker_id)s] %(message)s",
    datefmt="%H:%M:%S"
)

class Broker:
    def __init__(self, host="localhost", base_port=5000, registry_addr="tcp://localhost:5555"):
        self.host = host
        self.base_port = base_port
        self.registry_addr = registry_addr
        self.broker_id = str(uuid.uuid4())[:4]
        self.log = logging.LoggerAdapter(logging.getLogger(__name__), {"broker_id": self.broker_id})
        
        self.context = zmq.Context()
        self.running = False
        self.clients = {}  # user_id -> {sala, ts}
        self._lock = threading.Lock()
        
        # Sockets Ports
        self.p_video_in  = base_port + 1
        self.p_video_out = base_port + 2
        self.p_audio_in  = base_port + 3
        self.p_audio_out = base_port + 4
        self.p_text_in   = base_port + 5
        self.p_text_out  = base_port + 6
        self.p_control   = base_port + 7
        self.p_inter     = base_port + 8

        self.peers = {} # addr -> socket
        
        # Estatísticas
        self.stats = {"video": 0, "audio": 0, "text": 0}

    def _setup_sockets(self):
        # Media Sockets (XSUB/XPUB para padrão Pub/Sub robusto)
        # XSUB recebe de publishers locais
        self.v_in = self.context.socket(zmq.XSUB); self.v_in.bind(f"tcp://*:{self.p_video_in}")
        self.v_out = self.context.socket(zmq.XPUB); self.v_out.bind(f"tcp://*:{self.p_video_out}")
        
        self.a_in = self.context.socket(zmq.XSUB); self.a_in.bind(f"tcp://*:{self.p_audio_in}")
        self.a_out = self.context.socket(zmq.XPUB); self.a_out.bind(f"tcp://*:{self.p_audio_out}")
        
        self.t_in = self.context.socket(zmq.XSUB); self.t_in.bind(f"tcp://*:{self.p_text_in}")
        self.t_out = self.context.socket(zmq.XPUB); self.t_out.bind(f"tcp://*:{self.p_text_out}")

        # Controle e Registro
        self.control = self.context.socket(zmq.REP); self.control.bind(f"tcp://*:{self.p_control}")
        
        # Inter-broker ROUTER para malha distribuída
        self.inter = self.context.socket(zmq.ROUTER); self.inter.bind(f"tcp://*:{self.p_inter}")

    def _proxy_loop(self, xsub, xpub, name, type_code):
        """Proxy manual para permitir interceptação, auditoria e roteamento inter-broker."""
        self.log.info(f"Proxy {name} ativo")
        poller = zmq.Poller()
        poller.register(xsub, zmq.POLLIN)
        poller.register(xpub, zmq.POLLIN)
        
        while self.running:
            socks = dict(poller.poll(500))
            if xsub in socks:
                # Recebido de um publisher local
                msg = xsub.recv_multipart()
                # msg[0] = sala (tópico), msg[1] = payload
                xpub.send_multipart(msg)
                
                # Encaminha para outros brokers no cluster
                self._broadcast_to_cluster(type_code, msg)
                self.stats[name] += 1

            if xpub in socks:
                # Recebido de um subscriber local (ex: inscrição de tópico)
                msg = xpub.recv_multipart()
                xsub.send_multipart(msg)

    def _broadcast_to_cluster(self, type_code, msg):
        """Envia mensagem local para todos os outros brokers conhecidos."""
        # Estrutura inter-broker: [type_code, source_id, sala, data]
        inter_msg = [type_code.to_bytes(1, 'big'), self.broker_id.encode()] + msg
        with self._lock:
            for addr, sock in self.peers.items():
                try:
                    sock.send_multipart(inter_msg, zmq.NOBLOCK)
                except zmq.ZMQError:
                    pass

    def _inter_broker_receiver(self):
        """Processa mensagens vindas de outros brokers do cluster."""
        self.log.info("Processador de malha distribuída iniciado")
        while self.running:
            if self.inter.poll(500):
                # ZMQ ROUTER msg: [identity, type_code, source_id, sala, data]
                parts = self.inter.recv_multipart()
                if len(parts) < 5: continue
                
                type_code = int.from_bytes(parts[1], 'big')
                source_id = parts[2].decode()
                sala = parts[3]
                data = parts[4]
                
                # Evita loops (embora a topologia ROUTER/DEALER ajude)
                if source_id == self.broker_id: continue
                
                # Publica no XPUB local apenas
                if type_code == 0: self.v_out.send_multipart([sala, data])
                elif type_code == 1: self.a_out.send_multipart([sala, data])
                elif type_code == 2: self.t_out.send_multipart([sala, data])

    def _handle_control(self):
        """Lida com login, presença e estatísticas."""
        while self.running:
            if self.control.poll(500):
                msg = self.control.recv_json()
                action = msg.get("action")
                
                if action == "login":
                    user_id = msg.get("user_id")
                    sala = msg.get("sala", "A")
                    with self._lock:
                        self.clients[user_id] = {"sala": sala, "ts": time.time()}
                    self.log.info(f"Usuário {user_id} entrou na sala {sala}")
                    self.control.send_json({
                        "status": "ok", 
                        "broker_id": self.broker_id,
                        "ports": {
                            "video_in": self.p_video_in, "video_out": self.p_video_out,
                            "audio_in": self.p_audio_in, "audio_out": self.p_audio_out,
                            "text_in": self.p_text_in, "text_out": self.p_text_out,
                            "control": self.p_control
                        }
                    })
                elif action == "stats":
                    self.control.send_json({"status": "ok", "stats": self.stats, "clients": len(self.clients)})
                elif action == "heartbeat":
                    user_id = msg.get("user_id")
                    with self._lock:
                        if user_id in self.clients:
                            self.clients[user_id]["ts"] = time.time()
                    self.control.send_json({"status": "ok"})
                else:
                    self.control.send_json({"status": "error", "msg": "Ação inválida"})

    def _registry_sync_loop(self):
        """Sincroniza com o Registry e descobre novos parceiros de cluster."""
        reg_sock = self.context.socket(zmq.REQ)
        reg_sock.setsockopt(zmq.RCVTIMEO, 2000)
        reg_sock.connect(self.registry_addr)
        my_addr = f"{self.host}:{self.base_port}"
        
        while self.running:
            try:
                # 1. Heartbeat no Registry
                reg_sock.send_json({"action": "register", "address": my_addr})
                reg_sock.recv_json()
                
                # 2. Atualizar lista de peers
                reg_sock.send_json({"action": "list_brokers"})
                resp = reg_sock.recv_json()
                if resp.get("status") == "ok":
                    active_brokers = resp.get("brokers", [])
                    with self._lock:
                        for b_addr in active_brokers:
                            if b_addr != my_addr and b_addr not in self.peers:
                                self.log.info(f"Novo broker detectado no cluster: {b_addr}")
                                p_host, p_base = b_addr.split(":")
                                p_inter_port = int(p_base) + 8
                                dealer = self.context.socket(zmq.DEALER)
                                dealer.connect(f"tcp://{p_host}:{p_inter_port}")
                                self.peers[b_addr] = dealer
            except Exception:
                self.log.warning("Falha ao sincronizar com Registry")
            time.sleep(2)

    def start(self):
        self.running = True
        self._setup_sockets()
        
        # Threads de serviço
        threads = [
            threading.Thread(target=self._registry_sync_loop, daemon=True),
            threading.Thread(target=self._handle_control, daemon=True),
            threading.Thread(target=self._inter_broker_receiver, daemon=True),
            threading.Thread(target=self._proxy_loop, args=(self.v_in, self.v_out, "video", 0), daemon=True),
            threading.Thread(target=self._proxy_loop, args=(self.a_in, self.a_out, "audio", 1), daemon=True),
            threading.Thread(target=self._proxy_loop, args=(self.t_in, self.t_out, "text", 2), daemon=True),
        ]
        
        for t in threads: t.start()
        self.log.info(f"Broker rodando na porta base {self.base_port}. Cluster Ativo.")

    def stop(self):
        self.log.info("Finalizando broker...")
        self.running = False
        time.sleep(1)
        self.context.term()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000, help="Porta base do broker")
    args = parser.parse_args()
    
    broker = Broker(base_port=args.port)
    try:
        broker.start()
        while True: time.sleep(1)
    except KeyboardInterrupt:
        broker.stop()
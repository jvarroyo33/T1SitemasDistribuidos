# discovery/registry.py
import zmq
import threading
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [REGISTRY] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

REGISTRY_PORT = 5555
BROKER_TIMEOUT = 10  # segundos sem heartbeat para remover broker

class Registry:
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{REGISTRY_PORT}")
        self.brokers = {}  # address -> last_heartbeat
        self.running = False
        self._lock = threading.Lock()

    def _cleanup(self):
        """Remove brokers que pararam de enviar heartbeats."""
        while self.running:
            now = time.time()
            with self._lock:
                to_remove = [addr for addr, ts in self.brokers.items() if now - ts > BROKER_TIMEOUT]
                for addr in to_remove:
                    log.info(f"Removendo broker inativo: {addr}")
                    del self.brokers[addr]
            time.sleep(2)

    def start(self):
        self.running = True
        threading.Thread(target=self._cleanup, daemon=True).start()
        log.info(f"Registry iniciado na porta {REGISTRY_PORT}")
        
        while self.running:
            try:
                if not self.socket.poll(timeout=1000):
                    continue
                
                msg = self.socket.recv_json()
                action = msg.get("action")
                
                if action == "register":
                    addr = msg.get("address")
                    with self._lock:
                        self.brokers[addr] = time.time()
                    log.info(f"Broker registrado/heartbeat: {addr}")
                    self.socket.send_json({"status": "ok"})
                
                elif action == "get_broker":
                    with self._lock:
                        if not self.brokers:
                            self.socket.send_json({"status": "error", "msg": "Nenhum broker disponível"})
                        else:
                            # Retorna o broker com menos carga ou round-robin simples
                            addr = list(self.brokers.keys())[0]
                            self.socket.send_json({"status": "ok", "address": addr})
                
                elif action == "list_brokers":
                    with self._lock:
                        self.socket.send_json({"status": "ok", "brokers": list(self.brokers.keys())})
                
                else:
                    self.socket.send_json({"status": "error", "msg": "Ação desconhecida"})
            
            except zmq.ZMQError:
                break

    def stop(self):
        self.running = False
        self.context.term()

if __name__ == "__main__":
    r = Registry()
    try:
        r.start()
    except KeyboardInterrupt:
        r.stop()

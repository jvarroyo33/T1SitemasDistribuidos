# broker/broker.py
import zmq
import threading
import logging
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BROKER] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# Portas por canal de mídia
VIDEO_PUB_PORT  = 5001
AUDIO_PUB_PORT  = 5002
TEXT_PUB_PORT   = 5003

# Porta de controle (presença / registro de clientes)
CONTROL_PORT    = 5100


class Broker:
    def __init__(self):
        self.context   = zmq.Context()
        self.running   = False
        self.clients   = {}   # user_id -> {sala, timestamp}
        self._lock     = threading.Lock()

    # ------------------------------------------------------------------
    # Sockets
    # ------------------------------------------------------------------
    def _setup_sockets(self):
        # XSUB recebe de publishers; XPUB repassa para subscribers
        # Esse par faz o broker "transparente" — não precisa conhecer tópicos
        self.video_xsub  = self.context.socket(zmq.XSUB)
        self.video_xpub  = self.context.socket(zmq.XPUB)
        self.video_xsub.bind(f"tcp://*:{VIDEO_PUB_PORT}")
        self.video_xpub.bind(f"tcp://*:{VIDEO_PUB_PORT + 10}")   # 5011

        self.audio_xsub  = self.context.socket(zmq.XSUB)
        self.audio_xpub  = self.context.socket(zmq.XPUB)
        self.audio_xsub.bind(f"tcp://*:{AUDIO_PUB_PORT}")
        self.audio_xpub.bind(f"tcp://*:{AUDIO_PUB_PORT + 10}")   # 5012

        self.text_xsub   = self.context.socket(zmq.XSUB)
        self.text_xpub   = self.context.socket(zmq.XPUB)
        self.text_xsub.bind(f"tcp://*:{TEXT_PUB_PORT}")
        self.text_xpub.bind(f"tcp://*:{TEXT_PUB_PORT + 10}")     # 5013

        # Controle: REP responde requisições de login/logout/listagem
        self.control     = self.context.socket(zmq.REP)
        self.control.bind(f"tcp://*:{CONTROL_PORT}")

        log.info("Sockets prontos:")
        log.info(f"  Vídeo  → XSUB :{VIDEO_PUB_PORT}  | XPUB :{VIDEO_PUB_PORT+10}")
        log.info(f"  Áudio  → XSUB :{AUDIO_PUB_PORT}  | XPUB :{AUDIO_PUB_PORT+10}")
        log.info(f"  Texto  → XSUB :{TEXT_PUB_PORT}  | XPUB :{TEXT_PUB_PORT+10}")
        log.info(f"  Controle → REP :{CONTROL_PORT}")

    # ------------------------------------------------------------------
    # Proxy threads — cada canal roda em thread própria
    # ------------------------------------------------------------------
    def _proxy(self, xsub, xpub, nome):
        log.info(f"Proxy [{nome}] iniciado")
        try:
            zmq.proxy(xsub, xpub)
        except zmq.ZMQError as e:
            if self.running:
                log.error(f"Proxy [{nome}] erro: {e}")

    # ------------------------------------------------------------------
    # Controle: login / logout / lista de presença
    # ------------------------------------------------------------------
    def _handle_control(self):
        log.info("Loop de controle iniciado")
        while self.running:
            try:
                if not self.control.poll(timeout=500):   # 500 ms timeout
                    continue
                msg = self.control.recv_json()
                resp = self._process_control(msg)
                self.control.send_json(resp)
            except zmq.ZMQError as e:
                if self.running:
                    log.error(f"Controle erro: {e}")

    def _process_control(self, msg: dict) -> dict:
        action  = msg.get("action")
        user_id = msg.get("user_id", "unknown")
        sala    = msg.get("sala", "A")

        with self._lock:
            if action == "login":
                self.clients[user_id] = {"sala": sala, "ts": time.time()}
                log.info(f"LOGIN  {user_id} → sala {sala}  ({len(self.clients)} online)")
                return {"status": "ok", "msg": f"Bem-vindo, {user_id}"}

            elif action == "logout":
                self.clients.pop(user_id, None)
                log.info(f"LOGOUT {user_id}  ({len(self.clients)} online)")
                return {"status": "ok", "msg": "Até logo"}

            elif action == "list":
                return {"status": "ok", "clients": list(self.clients.keys())}

            elif action == "ping":
                return {"status": "pong"}

            else:
                return {"status": "error", "msg": f"Ação desconhecida: {action}"}

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------
    def start(self):
        self.running = True
        self._setup_sockets()

        threads = [
            threading.Thread(target=self._proxy,
                             args=(self.video_xsub, self.video_xpub, "vídeo"),
                             daemon=True),
            threading.Thread(target=self._proxy,
                             args=(self.audio_xsub, self.audio_xpub, "áudio"),
                             daemon=True),
            threading.Thread(target=self._proxy,
                             args=(self.text_xsub,  self.text_xpub,  "texto"),
                             daemon=True),
            threading.Thread(target=self._handle_control,
                             daemon=True),
        ]
        for t in threads:
            t.start()

        log.info("=== Broker rodando. Ctrl+C para encerrar ===")
        return threads

    def stop(self):
        log.info("Encerrando broker...")
        self.running = False
        self.context.term()
        log.info("Broker encerrado.")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
def main():
    broker = Broker()
    threads = broker.start()

    def handler(sig, frame):
        broker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  handler)
    signal.signal(signal.SIGTERM, handler)

    # Mantém a thread principal viva
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        broker.stop()


if __name__ == "__main__":
    main()
# identity/session.py
import uuid
import zmq
import logging

log = logging.getLogger(__name__)

BROKER_HOST     = "localhost"
CONTROL_PORT    = 5100
SALAS_VALIDAS   = [chr(c) for c in range(ord('A'), ord('L'))]  # A–K


class Session:
    def __init__(self, nome: str, sala: str = "A"):
        if sala not in SALAS_VALIDAS:
            raise ValueError(f"Sala inválida: {sala}. Use A–K.")

        self.user_id  = f"{nome}_{uuid.uuid4().hex[:6]}"
        self.nome     = nome
        self.sala     = sala
        self.online   = False

        self._ctx     = zmq.Context.instance()
        self._ctrl    = self._ctx.socket(zmq.REQ)
        self._ctrl.setsockopt(zmq.RCVTIMEO, 3000)   # timeout 3s
        self._ctrl.connect(f"tcp://{BROKER_HOST}:{CONTROL_PORT}")

    # ------------------------------------------------------------------
    def login(self) -> bool:
        try:
            self._ctrl.send_json({
                "action":  "login",
                "user_id": self.user_id,
                "sala":    self.sala,
            })
            resp = self._ctrl.recv_json()
            if resp.get("status") == "ok":
                self.online = True
                log.info(f"[SESSION] Login ok — {self.user_id} sala {self.sala}")
                return True
            log.error(f"[SESSION] Login falhou: {resp}")
            return False
        except zmq.ZMQError as e:
            log.error(f"[SESSION] Broker inacessível: {e}")
            return False

    def logout(self):
        if not self.online:
            return
        try:
            self._ctrl.send_json({
                "action":  "logout",
                "user_id": self.user_id,
            })
            self._ctrl.recv_json()
            self.online = False
            log.info(f"[SESSION] Logout — {self.user_id}")
        except zmq.ZMQError:
            pass

    def listar_clientes(self) -> list:
        try:
            self._ctrl.send_json({"action": "list"})
            resp = self._ctrl.recv_json()
            return resp.get("clients", [])
        except zmq.ZMQError:
            return []

    def ping(self) -> bool:
        try:
            self._ctrl.send_json({"action": "ping"})
            resp = self._ctrl.recv_json()
            return resp.get("status") == "pong"
        except zmq.ZMQError:
            return False

    def __repr__(self):
        return f"Session(user_id={self.user_id}, sala={self.sala}, online={self.online})"
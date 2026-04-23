# tests/test_cluster.py
import sys
import os
import time
import subprocess
import zmq
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_inter_broker_routing():
    print("\n--- Teste 2: Roteamento Inter-Broker (Cluster) ---")
    
    # 1. Iniciar Infraestrutura com portas seguras (7000 e 8000)
    print("[TEST] Iniciando Registry e 2 Brokers (7000 e 8000)...")
    reg_proc = subprocess.Popen([sys.executable, "discovery/registry.py"])
    time.sleep(1)
    b1_proc = subprocess.Popen([sys.executable, "broker/broker.py", "--port", "7000"])
    b2_proc = subprocess.Popen([sys.executable, "broker/broker.py", "--port", "8000"])
    time.sleep(5) # Tempo para brokers se descobrirem via Registry
    
    context = zmq.Context()
    
    # 2. Configurar Subscriber no Broker B (Base 8000 -> Texto Out = 8006)
    sub = context.socket(zmq.SUB)
    sub.connect("tcp://localhost:8006")
    sub.setsockopt(zmq.SUBSCRIBE, b"SALA_TESTE")
    
    # 3. Configurar Publisher no Broker A (Base 7000 -> Texto In = 7005)
    pub = context.socket(zmq.PUB)
    pub.connect("tcp://localhost:7005")
    
    received_msgs = []
    def sub_loop():
        # Polling para evitar bloqueio infinito
        if sub.poll(10000): # Espera até 10s
            msg = sub.recv_multipart()
            received_msgs.append(msg)

    t = threading.Thread(target=sub_loop)
    t.start()
    
    # 4. Enviar mensagem para Broker A
    print("[TEST] Enviando mensagem para Broker A...")
    time.sleep(2)
    pub.send_multipart([b"SALA_TESTE", b"Ola do Cluster!"])
    
    t.join(timeout=12)
    
    # 5. Verificar resultado
    success = False
    try:
        if len(received_msgs) > 0:
            topic, data = received_msgs[0]
            if topic == b"SALA_TESTE" and data == b"Ola do Cluster!":
                print("[OK] Mensagem viajou do Broker A para o Broker B com sucesso!")
                success = True
            else:
                print(f"[FALHA] Mensagem incorreta: {topic}, {data}")
        else:
            print("[FALHA] Mensagem não recebida pelo Broker B dentro do timeout.")
    finally:
        reg_proc.kill()
        b1_proc.kill()
        b2_proc.kill()
        context.term()
        if not success:
            raise Exception("Teste de cluster falhou.")

if __name__ == "__main__":
    try:
        test_inter_broker_routing()
        print("\n--- TESTE DE CLUSTER PASSOU! ---")
    except Exception as e:
        print(f"\n[ERRO] Teste falhou: {e}")
        sys.exit(1)

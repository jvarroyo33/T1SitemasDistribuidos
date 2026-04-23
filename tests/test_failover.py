# tests/test_failover.py
import sys
import os
import time
import subprocess
import zmq
from identity.session import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_failover_logic():
    print("\n--- Teste 3: Tolerância a Falhas (Failover) ---")
    
    # 1. Iniciar Registry e Broker A
    print("[TEST] Iniciando ambiente inicial...")
    reg_proc = subprocess.Popen([sys.executable, "discovery/registry.py"])
    time.sleep(1)
    b1_proc = subprocess.Popen([sys.executable, "broker/broker.py", "--port", "5000"])
    time.sleep(2)
    
    # 2. Cliente faz Login
    print("[TEST] Cliente conectando ao Broker A...")
    sess = Session("TestUser", "A")
    assert sess.login() is True
    print(f"[OK] Cliente logado no broker: {sess.broker_info['broker_id']}")
    
    # 3. Derrubar Broker A
    print("[TEST] Derrubando Broker A...")
    b1_proc.terminate()
    time.sleep(1)
    
    # 4. Iniciar Broker B para o failover
    print("[TEST] Iniciando Broker B para recuperação...")
    b2_proc = subprocess.Popen([sys.executable, "broker/broker.py", "--port", "6000"])
    
    # O loop de heartbeat do cliente deve detectar a falha e reconectar
    print("[TEST] Aguardando reconexão automática (timeout de HB)...")
    
    # Vamos forçar uma verificação ou esperar o loop
    success = False
    for i in range(15):
        if sess.online and sess.broker_info['ports']['control'] == 6007:
            success = True
            break
        time.sleep(1)
        
    try:
        assert success is True
        print(f"[OK] Cliente reconectado com sucesso ao Broker B (Porta {sess.broker_info['ports']['control']})!")
    finally:
        reg_proc.terminate()
        b2_proc.terminate()

if __name__ == "__main__":
    try:
        test_failover_logic()
        print("\n--- TESTE DE FAILOVER PASSOU! ---")
    except Exception as e:
        print(f"\n[ERRO] Teste falhou: {e}")
        sys.exit(1)

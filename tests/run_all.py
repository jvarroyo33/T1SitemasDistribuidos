# tests/run_all.py
import subprocess
import sys
import time

tests = ["test_registry.py", "test_cluster.py", "test_failover.py"]

def run():
    print("=== INICIANDO SUÍTE DE TESTES DO SISTEMA DISTRIBUÍDO ===\n")
    for test in tests:
        print(f"Executando {test}...")
        try:
            # Usando run com capture_output=False para que o output vá direto pro terminal
            # Isso ajuda o agente a ver o progresso em tempo real
            res = subprocess.run([sys.executable, f"tests/{test}"], timeout=60)
            
            if res.returncode == 0:
                print(f"\n[SUCESSO] {test}")
            else:
                print(f"\n[FALHA] {test} (Retorno: {res.returncode})")
        except subprocess.TimeoutExpired:
            print(f"\n[TIMEOUT] {test} excedeu o tempo limite.")
        except Exception as e:
            print(f"\n[ERRO] Falha ao rodar {test}: {e}")
        print("-" * 50)
        time.sleep(1) # Pequena pausa entre testes para limpeza de sockets

if __name__ == "__main__":
    run()

# Documentação Técnica: Videoconferência Distribuída com ZeroMQ

## 1. Arquitetura do Sistema

O sistema foi evoluído de um único broker central para uma arquitetura distribuída, resiliente e escalável, composta por três camadas principais:

### 1.1 Registry (Discovery Service)
O Registry atua como o "cérebro" da topologia, permitindo que o sistema seja dinâmico.
- **Registro Dinâmico**: Brokers se registram ao iniciar, informando seu endereço e porta base.
- **Monitoramento**: Implementa um sistema de *timeouts* para remover brokers inativos que param de enviar heartbeats.
- **Service Discovery**: Clientes consultam o Registry para obter o endereço de um broker disponível, permitindo balanceamento de carga e tolerância a falhas.
- **Padrão ZMQ**: `REQ/REP` (Porta 5555).

### 1.2 Cluster de Brokers (Malha Distribuída)
Múltiplos brokers cooperam para distribuir mídia em escala global.
- **Inter-Broker Mesh**: Utiliza o padrão `ROUTER/DEALER` para criar uma malha de comunicação. Cada broker é conectado aos seus pares.
- **Roteamento Inteligente**: Mensagens recebidas de clientes locais são marcadas com o `broker_id` de origem e propagadas para o cluster. Brokers receptores validam o ID para evitar loops infinitos de mensagens.
- **Distribuição Híbrida**: Utiliza `SUB/PUB` para o padrão *Publisher-Subscriber* local, garantindo que apenas interessados em determinadas salas recebam os dados.
- **Portas Dinâmicas**: Cada broker utiliza uma faixa de portas baseada em um deslocamento (`base_port + N`), evitando conflitos em execuções locais.

### 1.3 Cliente (Multithreaded)
Aplicação modular que separa as preocupações de captura, rede e interface.
- **CaptureManager**: Threads dedicadas para OpenCV (Vídeo) e PyAudio (Áudio).
- **Sender/Receiver**: Gerenciam a comunicação assíncrona com o broker atribuído.
- **Session Manager**: Responsável pelo ciclo de vida da conexão, incluindo o *failover* automático.

---

## 2. Padrões ZeroMQ Utilizados

| Canal | Padrão ZMQ | Justificativa |
| :--- | :--- | :--- |
| **Descoberta** | `REQ/REP` | Síncrono e confiável para registro de serviços. |
| **Controle/HB** | `REQ/REP` | Utilizado para login, estatísticas e batimentos cardíacos. |
| **Mídia Local** | `SUB/PUB` | Padrão Pub/Sub eficiente que permite interceptação e roteamento. |
| **Malha Cluster** | `ROUTER/DEALER` | Essencial para comunicação assíncrona bidirecional entre brokers. |

---

## 3. Qualidade de Serviço (QoS) e Resiliência

### 3.1 Vídeo Adaptativo (Bitrate Variável)
Uma das funcionalidades mais avançadas do projeto. O sistema monitora a saturação das filas de envio (`video_q`):
- **Cenário Ideal**: Qualidade JPEG 60 e resolução nativa.
- **Congestionamento Médio**: Redução da qualidade JPEG para 30.
- **Congestionamento Crítico**: Qualidade JPEG 15 e **redimensionamento do frame** (Resize 50%) para reduzir drasticamente o uso de banda.

### 3.2 Tolerância a Falhas (Failover)
O cliente monitora a saúde do broker através de respostas de controle. Se um broker falha:
1. O cliente detecta o timeout no heartbeat.
2. Consulta o **Registry** por um novo broker ativo.
3. Realiza o "re-login" e restabelece os sockets de mídia de forma transparente para o usuário.

---

## 4. Suíte de Testes Automatizada

Para validar a complexidade do sistema distribuído, foi desenvolvida uma suíte de testes:

- **`test_registry.py`**: Valida se o Registry gerencia corretamente a entrada e saída de brokers.
- **`test_cluster.py`**: Simula dois brokers em portas distintas (`7000` e `8000`) e valida se uma mensagem enviada ao primeiro chega ao assinante do segundo através da malha inter-broker.
- **`test_failover.py`**: Valida a capacidade do cliente de sobreviver à queda de um servidor.
- **`run_all.py`**: Script de execução em massa com monitoramento em tempo real.

---

## 5. Instruções de Execução

### Pré-requisitos
```bash
pip install -r requirements.txt
```

### Passo a Passo
1. **Registry**: `python discovery/registry.py`
2. **Brokers** (Abra quantos desejar em portas diferentes):
   - `python broker/broker.py --port 7000`
   - `python broker/broker.py --port 8000`
3. **Clientes**: `python client/client.py`

---
**Equipe**: Enzo Dezem Alves RA: 801743 , João .....,....
**Data**: 23/04/2026

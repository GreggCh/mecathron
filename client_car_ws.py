import websocket
import json
import threading
import time

# --- CONFIGURAÇÕES ---
# Lembre-se de substituir o IP pelo IP real do seu ESP32!
ESP32_IP = "172.16.105.43"  # Exemplo: Adapte ao IP do seu ESP32
WEBSOCKET_PORT = 81
WEBSOCKET_URL = f"ws://{ESP32_IP}:{WEBSOCKET_PORT}"

# Objeto global para armazenar o estado atual da telemetria
telemetria_atual = {}

# --- FUNÇÕES DE HANDLER WEBSOCKET ---

def on_message(ws, message):
    """Lida com mensagens recebidas (Telemetria)"""
    global telemetria_atual
    try:
        data = json.loads(message)
        # Se a mensagem for um objeto JSON válido, assume que é telemetria
        if isinstance(data, dict):
            telemetria_atual = data
            
            # Formatação simples para impressão da telemetria
            distancia = telemetria_atual.get('distancia_cm', 'N/A')
            motor1_vel = telemetria_atual.get('motor1', {}).get('vel', 'N/A')
            motor2_vel = telemetria_atual.get('motor2', {}).get('vel', 'N/A')
            sensor_tras = telemetria_atual.get('presenca', {}).get('tras', 'N/A')
            
            print(f"\n[TELEMETRIA] Distância: {distancia}cm | Sensor traseiro: {sensor_tras} | Motor 1 Vel: {motor1_vel} | Motor 2 Vel: {motor2_vel}", end="\r")
        else:
            # Pode ser uma mensagem de status/erro do ESP32
            print(f"\n[STATUS DO CARRO] {message}")

    except json.JSONDecodeError:
        print(f"\n[ERRO JSON] Mensagem não JSON: {message}")
    except Exception as e:
        print(f"\n[ERRO] Falha ao processar mensagem: {e}")

def on_error(ws, error):
    """Lida com erros da conexão"""
    print(f"\n[ERRO DE CONEXÃO] {error}")

def on_close(ws, close_status_code, close_msg):
    """Lida com o fechamento da conexão"""
    print(f"\n### Conexão Fechada (Status: {close_status_code}, Msg: {close_msg}) ###")

def on_open(ws):
    """Lida com a abertura da conexão e inicia o loop de controle"""
    print(f"### Conexão Aberta com {WEBSOCKET_URL} ###")
    
    # Inicia o thread para enviar comandos de controle
    control_thread = threading.Thread(target=send_commands_loop, args=(ws,))
    control_thread.daemon = True
    control_thread.start()

# --- FUNÇÃO DE CONTROLE DE COMANDOS ---

def send_command(ws, motor1_vel, motor2_vel):
    """Cria e envia o comando JSON para o ESP32"""
    comando = {
        "motor1_vel": motor1_vel,
        "motor2_vel": motor2_vel
    }
    
    try:
        ws.send(json.dumps(comando))
        # Opcional: print(f"Comando enviado: M1={motor1_vel}, M2={motor2_vel}")
    except websocket.WebSocketConnectionClosedException:
        print("\n[ERRO] Conexão fechada. Não foi possível enviar o comando.")
    except Exception as e:
        print(f"\n[ERRO] Falha ao enviar comando: {e}")

def send_commands_loop(ws):
    """Loop principal para demonstrar o envio de comandos"""
    
    # === SEQUÊNCIA DE MOVIMENTO DE EXEMPLO ===
    try:
        # 1. Parado
        print("\n[COMANDO] Carro parado (5s)...")
        send_command(ws, 0, 0)
        time.sleep(1)
        
        # 2. Frente Rápido
        print("\n[COMANDO] Movendo para frente (3s)...")
        send_command(ws, 255, 255)
        time.sleep(1)

        # 3. Girar Esquerda
        print("\n[COMANDO] Girando à esquerda (2s)...")
        send_command(ws, 200, -200)
        time.sleep(1)

        # 4. Ré Lento
        print("\n[COMANDO] Movendo em ré (3s)...")
        send_command(ws, -100, -100)
        time.sleep(1)

        # 5. Parar Novamente
        print("\n[COMANDO] Parando e encerrando (3s)...")
        send_command(ws, 0, 0)
        time.sleep(3)

    except Exception as e:
        print(f"\n[ERRO NO LOOP DE COMANDO] {e}")
    finally:
        # Garante que o carro pare se o loop terminar
        send_command(ws, 0, 0)
        print("\n[FINALIZADO] Loop de comandos concluído. Fechando conexão...")
        ws.close()

# --- INICIALIZAÇÃO ---

if __name__ == "__main__":
    # Define o modo de rastreamento para facilitar a depuração
    # websocket.enableTrace(True) 
    
    print(f"Tentando conectar a: {WEBSOCKET_URL}")

    # Cria a instância do WebSocket
    ws = websocket.WebSocketApp(
        WEBSOCKET_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # Roda a aplicação em um loop contínuo
    # O `run_forever` usa um loop síncrono para gerenciar a conexão e o recebimento de mensagens.
    # O envio de comandos é gerenciado por um thread separado (`send_commands_loop`).
    ws.run_forever()
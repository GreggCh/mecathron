import asyncio
import websockets
import json
import sys

# --- CONFIGURAÇÕES DE CONEXÃO (Devem corresponder ao servidor) ---
WEBSOCKET_URI = "ws://localhost:8765"

# ----------------------------------------------------------------------
# 1. Função Assíncrona para o Cliente WebSocket
# ----------------------------------------------------------------------

async def websocket_client():
    """
    Conecta-se ao servidor WebSocket, recebe e processa os dados JSON de detecção.
    """
    print(f"Tentando conectar ao servidor WebSocket em: {WEBSOCKET_URI}")

    try:
        # Tenta conectar ao servidor
        async with websockets.connect(WEBSOCKET_URI) as websocket:
            print("Conexão estabelecida com sucesso!")
            print("Aguardando dados de detecção do servidor...")
            print("-" * 50)
            
            # Loop para receber mensagens continuamente
            while True:
                # Recebe a mensagem (string JSON)
                message = await websocket.recv()
                
                try:
                    # Deserializa a string JSON para um objeto Python (lista de dicionários)
                    data = json.loads(message)
                    
                    # Processa e imprime os dados
                    print(f"\n[RECEIVED] Timestamp: {asyncio.get_event_loop().time():.2f}")
                    
                    if isinstance(data, list) and data:
                        for item in data:
                            personagem = item.get('personagem', 'DESCONHECIDO')
                            x = item.get('x_global', 'N/A')
                            y = item.get('y_global', 'N/A')
                            angulo = item.get('angulo_graus', 'N/A')

                            print(f"  > {personagem.upper()}:")
                            print(f"    - Posição (Global X, Y): ({x}, {y})")
                            print(f"    - Ângulo (Graus): {angulo}")
                    else:
                        print("  Dados recebidos vazios ou em formato inesperado.")
                        
                except json.JSONDecodeError:
                    print(f"[ERROR] Mensagem JSON inválida recebida: {message[:50]}...")
                except Exception as e:
                    print(f"[ERROR] Erro ao processar mensagem: {e}")

    except ConnectionRefusedError:
        print(f"\n[FATAL] Conexão recusada. O servidor não está rodando em {WEBSOCKET_URI} ou a porta está bloqueada.")
        print("Verifique se o 'main_detection.py' está em execução.")
    except websockets.exceptions.ConnectionClosedOK:
        print("\n[INFO] Conexão encerrada pelo servidor (OK).")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"\n[ERROR] Conexão perdida: {e}")
    except Exception as e:
        print(f"\n[FATAL] Ocorreu um erro inesperado: {e}")

# ----------------------------------------------------------------------
# 2. Ponto de Entrada
# ----------------------------------------------------------------------

if __name__ == "__main__":
    # Garante que o loop de evento asyncio seja executado
    try:
        asyncio.run(websocket_client())
    except KeyboardInterrupt:
        print("\nCliente encerrado pelo usuário (Ctrl+C).")
    except Exception as e:
        print(f"Ocorreu um erro no loop asyncio: {e}")
        sys.exit(1)
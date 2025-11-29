import asyncio
import websockets
import json
import sys

# --- CONFIGURAÇÕES DE CONEXÃO (Devem corresponder ao servidor) ---
WEBSOCKET_URI = "ws://192.168.1.101:8765"

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
                    # Deserializa a string JSON
                    data = json.loads(message)
                    
                    # --- NOVO PROCESSO DE LEITURA ---
                    
                    # O dado principal agora é um dicionário que contém "objetos" e "estado_jogo"
                    objetos = data.get('objetos', [])
                    estado_jogo = data.get('estado_jogo', {})
                    
                    print(f"\n[RECEIVED] Timestamp: {asyncio.get_event_loop().time():.2f}")
                    
                    # 1. PROCESSA ESTADO DO JOGO
                    power_active = estado_jogo.get('power_active', False)
                    speed_active = estado_jogo.get('speed_active', False)
                    power_time = estado_jogo.get('power_remaining_time', 0)
                    speed_time = estado_jogo.get('speed_remaining_time', 0)

                    print(f"## ESTADO DO JOGO ##")
                    print(f"  - POWER ACTIVE (Caçador): {power_active} ({power_time:.1f}s restantes)")
                    print(f"  - SPEED ACTIVE (Boost): {speed_active} ({speed_time:.1f}s restantes)")
                    
                    # 2. PROCESSA DADOS DE POSIÇÃO DOS PERSONAGENS
                    if isinstance(objetos, list) and objetos:
                        print(f"## DADOS DE POSIÇÃO ({len(objetos)} objetos) ##")
                        for item in objetos:
                            personagem = item.get('personagem', 'DESCONHECIDO')
                            x = item.get('x_global', 'N/A')
                            y = item.get('y_global', 'N/A')
                            angulo = item.get('angulo_graus', 'N/A')

                            print(f"  > {personagem.upper()}:")
                            print(f"    - Posição (Global X, Y): ({x}, {y})")
                            print(f"    - Ângulo (Graus): {angulo}")
                    else:
                        print("  Dados de objetos vazios.")
                        
                except json.JSONDecodeError:
                    print(f"[ERROR] Mensagem JSON inválida recebida: {message[:50]}...")
                except Exception as e:
                    print(f"[ERROR] Erro ao processar mensagem: {e}")

    except ConnectionRefusedError:
        print(f"\n[FATAL] Conexão recusada. O servidor não está rodando em {WEBSOCKET_URI} ou a porta está bloqueada.")
        print("Verifique se o 'mecathron_server.py' está em execução.")
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

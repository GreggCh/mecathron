import sys
# Força print imediato
sys.stdout.reconfigure(line_buffering=True)

import asyncio
import json
import pygame
import threading
import queue
import math
import time

try:
    import websocket # pip install websocket-client
    import websockets # pip install websockets
except ImportError:
    print("ERRO: Instale as libs: pip install websocket-client websockets")
    sys.exit()

# --- CONFIGURAÇÕES ---
WEBSOCKET_URI_GAME = "ws://127.0.0.1:8765"
WEBSOCKET_URI_CAR = "ws://192.168.1.102:81"
MEU_PERSONAGEM = "fantasma_1" # Confirme o nome no JSON!

# --- PARAMETROS DE MOVIMENTO ---
FREQ_CONTROLE = 0.2  # 5 Hz (1 / 5 = 0.2 segundos)

# Velocidades (0 a 255 - Ajuste conforme a potência do seu motor)
VEL_FRENTE = 130     # Velocidade de cruzeiro
VEL_CURVA_FORTE = 130 # Roda externa da curva
VEL_CURVA_FRACA = 90  # Roda interna (Positiva para andar pra frente fazendo arco)
VEL_RE = -100         # Para sair de travamentos

# --- FILAS E ESTADO ---
data_queue = queue.Queue()
command_queue = queue.Queue()
running = True

# Histórico para detectar travamento
historico_posicao = [] 
MAX_HISTORICO = 10 # Guarda os últimos 10 posições (~2 segundos a 5Hz)
MODO_DESTRAMENTO = False
TIMER_DESTRAMENTO = 0

# ==========================================
# 1. THREAD CARRO (Envia Comandos)
# ==========================================
def car_thread():
    ws = None
    while running:
        # Conexão
        if ws is None or not ws.connected:
            try:
                ws = websocket.create_connection(WEBSOCKET_URI_CAR, timeout=1)
                print(">>> [ROBÔ] Conectado.")
            except:
                time.sleep(1); continue

        # Envio
        try:
            m1, m2 = command_queue.get(timeout=0.2)
            msg = json.dumps({"motor1_vel": int(m1), "motor2_vel": int(m2)})
            ws.send(msg)
            # print(f"   -> Enviado: {m1}, {m2}") # Descomente para debug intenso
        except queue.Empty:
            pass
        except Exception:
            ws.close(); ws = None

# ==========================================
# 2. THREAD VISÃO (Recebe Dados)
# ==========================================
async def vision_loop():
    while running:
        try:
            async with websockets.connect(WEBSOCKET_URI_GAME) as ws:
                print(">>> [VISÃO] Conectado.")
                while running:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    # Mantém apenas o dado mais recente
                    with data_queue.mutex: data_queue.queue.clear()
                    data_queue.put(data)
        except:
            await asyncio.sleep(1)

def run_vision():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(vision_loop())

# ==========================================
# 3. MATEMÁTICA E LÓGICA
# ==========================================
def angulo_para_alvo(eu, alvo):
    dx = alvo['x_global'] - eu['x_global']
    dy = alvo['y_global'] - eu['y_global']
    # O eixo Y do OpenCV cresce para baixo, mas atan2 trata Y para cima padrão.
    # Se o ângulo do robô vier no padrão 0-360 horário, precisamos cuidar aqui.
    # Geralmente atan2(dy, dx) funciona bem se o ângulo do robô estiver calibrado igual.
    return math.degrees(math.atan2(dy, dx))

def normalizar_erro(erro):
    # Traz o erro para o intervalo [-180, 180]
    return (erro + 180) % 360 - 180

def checar_travamento(pos_atual):
    """ Retorna True se o robô estiver parado no mesmo lugar (pixel) há muito tempo """
    global historico_posicao
    
    historico_posicao.append(pos_atual)
    if len(historico_posicao) > MAX_HISTORICO:
        historico_posicao.pop(0)
    
    if len(historico_posicao) < MAX_HISTORICO:
        return False

    # Calcula deslocamento total nos últimos N frames
    p_ini = historico_posicao[0]
    p_fim = historico_posicao[-1]
    dist = math.hypot(p_fim[0] - p_ini[0], p_fim[1] - p_ini[1])
    
    # Se moveu menos de 10 pixels em 2 segundos e estamos tentando andar... travou.
    return dist < 10

# ==========================================
# 4. LOOP PRINCIPAL (5 Hz)
# ==========================================
def main():
    global running, MODO_DESTRAMENTO, TIMER_DESTRAMENTO
    
    # Inicializa Pygame (Janela de Status)
    pygame.init()
    screen = pygame.display.set_mode((400, 300))
    pygame.display.set_caption(f"Controle 5Hz: {MEU_PERSONAGEM}")
    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()

    # Inicia Threads
    threading.Thread(target=car_thread, daemon=True).start()
    threading.Thread(target=run_vision, daemon=True).start()

    last_process_time = time.time()
    status_msg = "Iniciando..."
    cmd_txt = "0, 0"

    print(f">>> INICIANDO CONTROLE MALHA FECHADA ({1/FREQ_CONTROLE:.0f} Hz)")

    while running:
        # Eventos UI
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False

        # Verifica Timer de Controle (5Hz)
        now = time.time()
        if now - last_process_time >= FREQ_CONTROLE:
            last_process_time = now
            
            # 1. Obter Dados
            if data_queue.empty():
                continue
            
            data = data_queue.get()
            estado = data.get("estado_jogo", {})
            objetos = data.get("objetos", [])

            # 2. Regra de PAUSA / GAME OVER
            if estado.get("paused") or estado.get("game_over"):
                status_msg = "JOGO PAUSADO / GAME OVER"
                command_queue.put((0, 0))
                # Limpa histórico para não detectar travamento enquanto pausado
                historico_posicao = [] 
                print(f"[5Hz] {status_msg} -> Motores 0")
                continue

            # 3. Identificar Entidades
            eu = next((o for o in objetos if o['personagem'] == MEU_PERSONAGEM), None)
            # Alvo: Tenta achar 'bola' ou 'fantasma' (genérico)
            alvo = next((o for o in objetos if 'bola' in o['personagem'] or 'fantasma' in o['personagem']), None)

            if eu and alvo:
                # --- LÓGICA DE DESTRAVAMENTO ---
                if MODO_DESTRAMENTO:
                    # Se ativado, anda de ré por 1 segundo
                    status_msg = "!!! DESTRAVANDO (RÉ) !!!"
                    command_queue.put((VEL_RE, VEL_RE))
                    TIMER_DESTRAMENTO -= FREQ_CONTROLE
                    if TIMER_DESTRAMENTO <= 0:
                        MODO_DESTRAMENTO = False
                        historico_posicao = [] # Reset histórico
                    print(f"[5Hz] {status_msg}")
                    continue

                # Verifica se travou (Se estamos tentando mover mas a posição (x,y) não muda)
                pos_xy = (eu['x_global'], eu['y_global'])
                if checar_travamento(pos_xy):
                    MODO_DESTRAMENTO = True
                    TIMER_DESTRAMENTO = 1.0 # 1 segundo de ré
                    continue
                # -------------------------------

                # --- CÁLCULO DE NAVEGAÇÃO ---
                ang_robo = float(eu['angulo_graus'])
                ang_alvo = angulo_para_alvo(eu, alvo)
                erro = normalizar_erro(ang_alvo - ang_robo)

                m1, m2 = 0, 0
                
                # Zona Morta (Alinhado)
                if abs(erro) < 15: 
                    status_msg = f"FRENTE (Erro {erro:.1f})"
                    m1, m2 = VEL_FRENTE, VEL_FRENTE
                
                # Curva para Direita (Erro Positivo)
                # IMPORTANTE: Se o robô virar para a esquerda, inverta este bloco!
                elif erro > 0:
                    status_msg = f"CURVA DIREITA (Erro {erro:.1f})"
                    m1 = VEL_CURVA_FORTE  # Esquerda Força
                    m2 = VEL_CURVA_FRACA  # Direita Suave (mas positiva!)
                
                # Curva para Esquerda (Erro Negativo)
                else:
                    status_msg = f"CURVA ESQUERDA (Erro {erro:.1f})"
                    m1 = VEL_CURVA_FRACA  # Esquerda Suave
                    m2 = VEL_CURVA_FORTE  # Direita Força

                cmd_txt = f"{m1}, {m2}"
                command_queue.put((m1, m2))
                print(f"[5Hz] {status_msg} | Cmd: {m1}, {m2}")

            elif not eu:
                status_msg = f"PROCURANDO {MEU_PERSONAGEM}..."
                command_queue.put((0, 0))
                print(f"[5Hz] {status_msg}")
            else:
                status_msg = "SEM ALVO VISÍVEL"
                command_queue.put((0, 0))

        # --- UI Pygame ---
        screen.fill((0,0,0))
        lines = [
            f"Robo: {MEU_PERSONAGEM}",
            f"Status: {status_msg}",
            f"Comando Atual: {cmd_txt}",
            f"Freq: 5Hz"
        ]
        y = 20
        for l in lines:
            color = (255, 50, 50) if "DESTRAVANDO" in status_msg else (0, 255, 0)
            screen.blit(font.render(l, True, color), (20, y))
            y += 30
        pygame.display.flip()
        
    pygame.quit()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
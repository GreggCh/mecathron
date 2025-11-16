# main_detection.py (Versão com controle de exibição de imagem e FILTRO DE SUAVIZAÇÃO)
import cv2
import numpy as np
import sys
import json
import asyncio
from websockets.server import serve

# --- CONFIGURAÇÃO DE FILTRO ---
# Fator de suavização (Alpha) para o filtro de média ponderada.
# 0.05 a 0.20 é um bom ponto de partida. Quanto menor, mais suave, mas mais atraso.
ALPHA = 0.15 
# Dicionário para armazenar a última posição suavizada de cada personagem
LAST_SMOOTHED_POSITIONS = {} 

# --- CONFIGURAÇÃO DE CORES DE SAÍDA E PARÂMETROS GLOBAIS ---
LOWER_DARK_GREEN = np.array([40, 50, 50])
UPPER_DARK_GREEN = np.array([80, 255, 150]) 
MIN_GREEN_AREA = 500 

CONFIG_FILE = "config_arena_pac_man.json"
WEBSOCKET_PORT = 8765
WEBSOCKET_HOST = "127.0.0.1" 

CONFIG = {}
ROI_COORDS = None
ZONA_GATILHO_COORDS = {} # Variável para armazenar as 4 zonas (zona_1, zona_2, etc.)
CARROS_DETECTADOS = []
MOSTRAR_IMAGEM = True

RAIO_PERSONAGEM_PIXELS = 60
POWER_UP = False

# --- CARREGAR CONFIGURAÇÃO ---
try:
    with open(CONFIG_FILE, 'r') as f:
        CONFIG = json.load(f)
        ROI_COORDS = tuple(CONFIG['ROI'])
        CORES_CONFIG = CONFIG['Cores']
        
        # --- NOVO: Carregar coordenadas das Zonas de Gatilho ---
        # Assume-se que o arquivo de calibração salva as zonas em "Zonas"
        if 'Zonas' in CONFIG:
            ZONA_GATILHO_COORDS = CONFIG['Zonas']
            print(f"Zonas de Gatilho carregadas: {len(ZONA_GATILHO_COORDS)} zonas.")
        else:
            print("AVISO: Nenhuma zona de gatilho encontrada na configuração.")
        
        print(f"Configuração carregada com {len(CORES_CONFIG)} personagens.")
        
        # ... (restante da inicialização de LAST_SMOOTHED_POSITIONS)
        for nome in CORES_CONFIG.keys():
            LAST_SMOOTHED_POSITIONS[nome] = None
            
except FileNotFoundError:
    print(f"ERRO: Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
    print("Execute 'calibracao.py' primeiro para configurar a arena e as cores.")
    sys.exit()
except json.JSONDecodeError:
    print(f"ERRO: Arquivo de configuração '{CONFIG_FILE}' inválido.")
    sys.exit()

def checar_zonas(pacman_pos_global, zonas_coords):
    """
    Verifica em qual zona de gatilho o Pac-Man está posicionado.

    Argumentos:
        pacman_pos_global (tuple): (x, y) global (no frame original) do centroide do Pac-Man.
        zonas_coords (dict): Dicionário com as coordenadas [x, y, w, h] de cada zona.

    Retorna:
        dict: O status de cada zona (True/False).
    """
    zonas_status = {key: False for key in zonas_coords.keys()}
    
    if pacman_pos_global is None:
        return zonas_status

    px, py = pacman_pos_global

    for nome_zona, [zx, zy, zw, zh] in zonas_coords.items():
        # A detecção de zona é baseada nas coordenadas GLOBAIS (do frame original)
        # O ROI principal da arena é para processamento, não para a localização global.
        
        # Colisão ocorre se o ponto (px, py) estiver dentro do retângulo [zx, zy, zw, zh]
        if (px >= zx and px <= zx + zw) and (py >= zy and py <= zy + zh):
            zonas_status[nome_zona] = True
            
    return zonas_status

def checar_colisoes(objetos_detectados_filtrados):
    """
    Verifica se algum fantasma colidiu com o Pac-Man.
    
    Argumentos:
        objetos_detectados_filtrados (list): Lista de dicionários com os dados 
                                              filtrados (posições globais).
    Retorna:
        list: Uma lista de nomes de fantasmas que colidiram com o Pac-Man.
    """
    colisoes_encontradas = []
    pacman_pos = None
    fantasmas = {}

    # 1. Separar o Pac-Man dos Fantasmas
    for obj in objetos_detectados_filtrados:
        nome = obj['personagem']
        
        # Coordenadas já estão suavizadas e globais (em pixels)
        pos = (obj['x_global'], obj['y_global'])
        
        if 'pac-man' in nome:
            pacman_pos = pos
        elif 'fantasma' in nome:
            fantasmas[nome] = pos

    if pacman_pos is None or not fantasmas:
        return [] # Não há colisão se o Pac-Man ou Fantasmas estiverem ausentes

    px, py = pacman_pos
    
    # 2. Calcular a Distância e Checar Colisão
    # A colisão ocorre quando a distância entre os centros (d) é menor que 
    # a soma dos raios (R_pacman + R_fantasma). Como os raios são iguais, 
    # o limite de distância é 2 * RAIO_PERSONAGEM_PIXELS.
    limite_distancia_quadrado = (2 * RAIO_PERSONAGEM_PIXELS) ** 2

    for nome_fantasma, (fx, fy) in fantasmas.items():
        # Distância Euclidiana ao quadrado (para evitar a raiz quadrada, que é lenta)
        distancia_quadrado = (px - fx)**2 + (py - fy)**2
        
        if distancia_quadrado < limite_distancia_quadrado:
            colisoes_encontradas.append(nome_fantasma)
            
    return colisoes_encontradas

# ----------------------------------------------------------------------
# 3. Funções de Detecção e WS
# ----------------------------------------------------------------------

# Mantida a função detectar_cor_parada (inalterada)
def detectar_cor_parada(frame):
    """ Verifica a presença da cor Verde Escuro. """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_DARK_GREEN, UPPER_DARK_GREEN)
    
    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contornos:
        maior_contorno = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(maior_contorno) >= MIN_GREEN_AREA:
            return True
    return False

def processar_frame(frame):
    """
    Processa um único frame para detectar todos os personagens configurados.
    """
    frame_processado = frame.copy()
    resultados = []

    for nome_personagem, cor_hsv in CORES_CONFIG.items():
        lower_hsv = np.array(cor_hsv['lower'])
        upper_hsv = np.array(cor_hsv['upper'])
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_hsv, upper_hsv)
        
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=1)

        contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contornos:
            continue # Nenhuma detecção, pula para o próximo personagem

        # Encontra o maior contorno (assume-se que é o personagem)
        contorno = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(contorno) < 50: 
            continue

        rect = cv2.minAreaRect(contorno)
        (x_center, y_center), (width, height), angle = rect
        
        posicao_x_raw = int(x_center)
        posicao_y_raw = int(y_center)
        
        if width < height:
            angle = angle - 90 
        
        angulo_final_raw = -angle
        if angulo_final_raw < 0:
            angulo_final_raw += 360
        angulo_final_raw = round(angulo_final_raw, 2)
        
        # ------------------------------------------------------------------
        # --- APLICAÇÃO DO FILTRO DE SUAVIZAÇÃO (Exponential Smoothing) ---
        # ------------------------------------------------------------------
        
        last_pos = LAST_SMOOTHED_POSITIONS[nome_personagem]
        
        if last_pos is None:
            # Primeira detecção: define a posição atual como a posição suavizada
            smoothed_x = posicao_x_raw
            smoothed_y = posicao_y_raw
            smoothed_angle = angulo_final_raw
        else:
            # Aplica o filtro nos três valores: X, Y, Ângulo
            smoothed_x = int(ALPHA * posicao_x_raw + (1 - ALPHA) * last_pos['x'])
            smoothed_y = int(ALPHA * posicao_y_raw + (1 - ALPHA) * last_pos['y'])
            
            # Suavização do ângulo deve tratar a transição 360 -> 0 ou 0 -> 360
            # Para simplificar, usamos a média ponderada, mas a interpolação deve 
            # ser feita na forma de vetor (seno/cosseno) para ângulos, o que é mais complexo.
            # Vamos usar o filtro simples, mas ciente da limitação em transições abruptas.
            smoothed_angle = ALPHA * angulo_final_raw + (1 - ALPHA) * last_pos['angulo']
            
            # Normaliza o ângulo suavizado (se necessário)
            smoothed_angle = smoothed_angle % 360

        # Atualiza a variável global de posições suavizadas
        LAST_SMOOTHED_POSITIONS[nome_personagem] = {
            'x': smoothed_x,
            'y': smoothed_y,
            'angulo': smoothed_angle
        }
        
        # ------------------------------------------------------------------

        # Desenha no frame USANDO AS POSIÇÕES SUAVIZADAS
        if MOSTRAR_IMAGEM:
            # Usamos a posição bruta para desenhar o retângulo (mais preciso para o objeto)
            box = cv2.boxPoints(rect)
            box = np.int32(box)
            
            bgr_color = (255, 0, 0) 
            if 'pac-man' in nome_personagem:
                bgr_color = (0, 255, 255)
            
            cv2.drawContours(frame_processado, [box], 0, bgr_color, 2) 
            
            # O CENTRO É DESENHADO USANDO A POSIÇÃO SUAVIZADA
            cv2.circle(frame_processado, (smoothed_x, smoothed_y), 5, (0, 0, 255), -1)

        resultados.append({
            "personagem": nome_personagem,
            "x_arena": smoothed_x, 
            "y_arena": smoothed_y, 
            "angulo_graus": round(smoothed_angle, 2)
        })

    return frame_processado, resultados


async def websocket_handler(websocket, path):
    """ Handler para cada conexão WebSocket. """
    print(f"[WS] Nova conexão estabelecida.")
    global CARROS_DETECTADOS

    try:
        while True:
            data_to_send = CARROS_DETECTADOS 
            if data_to_send:
                json_data = json.dumps(data_to_send)
                await websocket.send(json_data)
            
            await asyncio.sleep(0.1) 
            
    except Exception as e:
        print(f"[WS] Conexão fechada ou erro: {e}")
    finally:
        pass


def start_websocket_server():
    """ Inicia o servidor WebSocket. """
    print(f"[WS] Servidor WebSocket iniciado em ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
    return serve(websocket_handler, WEBSOCKET_HOST, WEBSOCKET_PORT)


# ----------------------------------------------------------------------
# 4. Loop Principal (SÍNCRONO - OpenCV)
# ----------------------------------------------------------------------

def opencv_loop(loop, roi_coords):
    global CARROS_DETECTADOS # Renomeada para OBJETOS_DETECTADOS para clareza
    global CARROS_DETECTADOS, ZONA_GATILHO_COORDS # Incluir ZONA_GATILHO_COORDS
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    if not cap.isOpened():
        print("Erro fatal: Câmera não pôde ser aberta.")
        sys.exit()

    x_roi, y_roi, w_roi, h_roi = roi_coords
    
    wait_delay = 1 if MOSTRAR_IMAGEM else 2 
    
    while cap.isOpened():
        ret, frame_original = cap.read()
        if not ret:
            break
            
        # ... (Checagem de cor de parada) ...

        frame_arena = frame_original[y_roi : y_roi + h_roi, x_roi : x_roi + w_roi]
        
        frame_processado_arena, objetos_detectados = processar_frame(frame_arena)
        
        # --- ATUALIZAÇÃO GLOBAL E FILTRADA ---
        dados_filtrados_e_globais = []
        pacman_pos_global = None
        
        for obj in objetos_detectados:
            x_global = obj['x_arena'] + x_roi
            y_global = obj['y_arena'] + y_roi
            
            dados_filtrados_e_globais.append({
                "personagem": obj['personagem'],
                "x_global": x_global, 
                "y_global": y_global,
                "angulo_graus": obj['angulo_graus']
            })
            
            # 1. Obter a posição global do Pac-Man
            if 'pac-man' in obj['personagem']:
                pacman_pos_global = (x_global, y_global)

        # 2. CHECAR ZONAS
        status_zonas = checar_zonas(pacman_pos_global, ZONA_GATILHO_COORDS)
        
        # 3. Empacotar TUDO para o WebSocket
        dados_websocket = {
            "objetos": dados_filtrados_e_globais,
            "zonas": status_zonas
        }
        
        # Atualiza a variável global para o WebSocket
        CARROS_DETECTADOS = dados_websocket
        
        # 4. CHECAR COLISÕES (usa a lista de objetos, não o dicionário empacotado)
        colisoes = checar_colisoes(dados_filtrados_e_globais)

        if colisoes:
            print(f"!!! COLISÃO DETECTADA: Pac-Man tocou em {', '.join(colisoes)} !!!")
            # Opcional: Enviar um alerta de colisão via WebSocket ou mudar o estado do jogo
            
            # Desenha um círculo de alerta no frame original (para colisão)
            if MOSTRAR_IMAGEM:
                 for obj in dados_filtrados_e_globais:
                     if obj['personagem'] == 'pac-man':
                         # Desenha um grande círculo vermelho no Pac-Man em caso de colisão
                         cv2.circle(frame_original, (obj['x_global'], obj['y_global']), 
                                    RAIO_PERSONAGEM_PIXELS + 10, (0, 0, 255), 3)


        # --- VISUALIZAÇÃO --- (O restante do loop de visualização permanece o mesmo)
        if MOSTRAR_IMAGEM:
            
            objetos_para_desenho = CARROS_DETECTADOS.get("objetos", [])

            frame_original[y_roi : y_roi + h_roi, x_roi : x_roi + w_roi] = frame_processado_arena
            cv2.rectangle(frame_original, (x_roi, y_roi), (x_roi + w_roi, y_roi + h_roi), (255, 255, 0), 3)

            for obj in objetos_para_desenho:
                 cv2.putText(frame_original, 
                            f"{obj['personagem']}", 
                            (obj['x_global'] - 50, obj['y_global'] - 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # Adiciona uma legenda para o raio de colisão (opcional)
            cv2.putText(frame_original, 
                        f"Raio Colisao: {RAIO_PERSONAGEM_PIXELS}px", 
                        (frame_original.shape[1] - 200, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            cv2.imshow('Detecção de Personagens (Websocket ON)', frame_original)

            for nome_zona, [zx, zy, zw, zh] in ZONA_GATILHO_COORDS.items():
                cor_zona = (255, 0, 0) # Cor Padrão: Azul
                
                # Se a zona estiver ativa, muda a cor para verde
                if status_zonas.get(nome_zona, False):
                     cor_zona = (0, 255, 0) # Ativa: Verde
                     POWER_UP = True
                     print(f"Powerup: {POWER_UP}")
                     
                cv2.rectangle(frame_original, (zx, zy), (zx + zw, zy + zh), cor_zona, 2)
                cv2.putText(frame_original, nome_zona.upper(), (zx, zy - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor_zona, 1)
        
        y_offset = frame_original.shape[0] - 80
        for i, (nome, status) in enumerate(status_zonas.items()):
                cor_texto = (0, 255, 0) if status else (0, 0, 255)
                cv2.putText(frame_original, 
                        f"{nome}: {status}", 
                        (frame_original.shape[1] - 250, y_offset + i * 20), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor_texto, 1)


        cv2.imshow('Detecção de Personagens (Websocket ON)', frame_original)
        
        if cv2.waitKey(wait_delay) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    # Para o loop assíncrono para garantir o fechamento limpo
    if loop.is_running():
        loop.stop()
    print("Loop OpenCV encerrado. Encerrando servidor WebSocket.")


# ----------------------------------------------------------------------
# 5. Ponto de Entrada Principal
# ----------------------------------------------------------------------

if __name__ == "__main__":
    
    if not ROI_COORDS:
        sys.exit() 

    loop = asyncio.get_event_loop()
    
    ws_server = loop.run_until_complete(start_websocket_server())
    
    loop.run_in_executor(None, opencv_loop, loop, ROI_COORDS)
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nPrograma encerrado por interrupção do usuário (Ctrl+C).")
    finally:
        ws_server.close()
        loop.run_until_complete(ws_server.wait_closed())
        loop.close()
        print("Programa totalmente encerrado.")
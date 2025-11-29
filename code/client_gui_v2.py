import asyncio
import websockets
import json
import pygame
import threading
import queue
import sys
import math

# --- CONFIGURAÇÕES VISUAIS ---
WEBSOCKET_URI = "ws://127.0.0.1:8765"
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
SCREEN_TITLE = "Cliente Pac-Man Arena"
BACKGROUND_COLOR = (10, 10, 10)

# AJUSTE DE ESCALA (Mapeamento)
X_OFFSET = 50
Y_OFFSET = 50
SCALE_FACTOR = 0.7 

# Cores
COLOR_PACMAN = (255, 255, 0)
COLOR_PACMAN_HUNTER = (255, 100, 0)
COLOR_FANTASMA = (255, 0, 0)
COLOR_FANTASMA_VULNERAVEL = (0, 0, 255)
COLOR_TEXTO = (255, 255, 255)

# --- CONFIGURAÇÃO DE ÁUDIO (Volumes: 0.0 a 1.0) ---
VOLUMES = {
    "background_music": 0.3, # Música de fundo (mais baixo)
    "power_loop": 0.6,       # Som contínuo do modo caçador
    "start": 0.7,
    "death": 0.8,
    "eat_ghost": 1.0,        # Som alto para impacto
    "score": 0.4,            # Som sutil para coleta de pontos
    "gameover": 1.0
}

data_queue = queue.Queue()

# --- WEBSOCKET THREAD ---
async def websocket_client_async():
    try:
        async with websockets.connect(WEBSOCKET_URI) as websocket:
            while True:
                msg = await websocket.recv()
                try:
                    data = json.loads(msg)
                    if isinstance(data, dict): data_queue.put(data)
                    print(data)
                except: pass
    except Exception as e:
        print(f"WS Error: {e}"); data_queue.put(None)

def start_ws_thread():
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(websocket_client_async())
        loop.close()
    t = threading.Thread(target=run, daemon=True); t.start()
    return t

# --- DRAWING ---
def draw_rotated_rect(surface, color, cx, cy, w, h, angle):
    rect = pygame.Rect(0, 0, w, h); rect.center = (cx, cy)
    surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(surf, color, (0, 0, w, h))
    rot_surf = pygame.transform.rotate(surf, -angle)
    surface.blit(rot_surf, rot_surf.get_rect(center=rect.center))

def draw_pacman(surface, cx, cy, r, angle, is_hunter):
    color = COLOR_PACMAN_HUNTER if is_hunter else COLOR_PACMAN
    pygame.draw.circle(surface, color, (cx, cy), r)
    rad = math.radians(angle)
    ex = cx + r * math.cos(rad); ey = cy - r * math.sin(rad)
    pygame.draw.line(surface, (0,0,0), (cx, cy), (ex, ey), 3)

# --- SISTEMA DE SOM (Helper) ---
def load_sound(filename, volume_key):
    """ Carrega um efeito sonoro e aplica o volume configurado. """
    try:
        snd = pygame.mixer.Sound(filename)
        vol = VOLUMES.get(volume_key, 0.5)
        snd.set_volume(vol)
        return snd
    except FileNotFoundError:
        print(f"AVISO: '{filename}' não encontrado.")
        return None

# --- PYGAME LOOP ---
def pygame_loop():
    pygame.init()
    pygame.mixer.init() # Inicializa o sistema de som
    
    # Canais reservados (opcional, ajuda a organizar)
    pygame.mixer.set_num_channels(16)

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(SCREEN_TITLE)
    clock = pygame.time.Clock()
    
    font_main = pygame.font.Font(None, 24)
    font_hud = pygame.font.Font(None, 40)
    font_big = pygame.font.Font(None, 80)
    
    # ---------------------------------------------------------
    # 1. CARREGAMENTO DE ÁUDIO
    # ---------------------------------------------------------
    
    # A. Música de Fundo (Stream)
    try:
        # Use um arquivo .mp3 ou .wav longo para o fundo
        pygame.mixer.music.load("sons/ghost-siren-sound.mp3") 
        pygame.mixer.music.set_volume(VOLUMES["background_music"])
        pygame.mixer.music.play(-1) # -1 = Loop infinito
    except pygame.error:
        print("AVISO: Música de fundo 'background.mp3' não encontrada.")

    # B. Efeitos Sonoros (RAM)
    sounds = {
        "start": load_sound("sons/start.wav", "start"),
        "power_loop": load_sound("sons/power_up.mp3", "power_loop"), # Som contínuo (sirene)
        "death": load_sound("sons/pacman_death.wav", "death"),
        "eat_ghost": load_sound("sons/eat_ghost.wav", "eat_ghost"),
        "gameover": load_sound("sons/gameover.wav", "gameover"),
        "score": load_sound("sons/pacman_chomp.wav", "score")
    }

    # Toca som de início
    if sounds["start"]: sounds["start"].play()

    running = True
    current_data = {"objetos": [], "estado_jogo": {}, "coletas": {}}
    
    # --- VARIÁVEIS DE CONTROLE DE ÁUDIO ---
    last_power_active = False
    last_lives = 3
    last_score = 0
    last_game_over = False
    
    # Controle de pausa de áudio
    audio_paused = False
    
    # Controle específico do loop do power-up
    power_sound_channel = None 

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                running = False
        
        try:
            while not data_queue.empty():
                d = data_queue.get_nowait()
                if d is None: running = False
                else: current_data = d
        except: pass

        if not running: break

        screen.fill(BACKGROUND_COLOR)
        
        # Extrair dados
        objetos = current_data.get("objetos", [])
        estado = current_data.get("estado_jogo", {})
        
        power_active = estado.get("power_active", False)
        lives = estado.get("lives", 3)
        score = estado.get("score", 0)
        time_rem = estado.get("time_remaining", 0)
        paused = estado.get("paused", False)
        game_over = estado.get("game_over", False)
        immunity = estado.get("immunity", False)

        # ---------------------------------------------------------
        # 2. GERENCIAMENTO DE ÁUDIO (PAUSA E LOOPS)
        # ---------------------------------------------------------

        # A. Pausa Global (Mute quando o jogo para)
        if paused and not audio_paused:
            pygame.mixer.music.pause() # Pausa música de fundo
            pygame.mixer.pause()       # Pausa todos os efeitos sonoros
            audio_paused = True
        elif not paused and audio_paused:
            pygame.mixer.music.unpause()
            pygame.mixer.unpause()
            audio_paused = False

        # Se o jogo não estiver pausado, gerenciamos os gatilhos
        if not paused:
            
            # B. Gerenciamento do Loop de Power-Up
            if power_active:
                # Se o som existe e o canal não está tocando (ou é None), inicia o loop
                if sounds["power_loop"] and (power_sound_channel is None or not power_sound_channel.get_busy()):
                    power_sound_channel = sounds["power_loop"].play(loops=-1) # Loop infinito
            else:
                # Se o power acabou, para o som imediatamente
                if sounds["power_loop"]:
                    sounds["power_loop"].stop()
                    power_sound_channel = None

            # C. Gatilhos de Eventos Únicos
            
            # Perdeu vida
            if lives < last_lives:
                if sounds["death"]: sounds["death"].play()
                # Para o loop do power-up se morrer
                if sounds["power_loop"]: sounds["power_loop"].stop()
            
            # Ganhou Pontos
            if score > last_score:
                if (score - last_score) >= 50:
                    if sounds["eat_ghost"]: sounds["eat_ghost"].play()
                else:
                    if sounds["score"]: sounds["score"].play()

            # Game Over
            if game_over and not last_game_over:
                pygame.mixer.music.stop() # Para a música de fundo
                if sounds["power_loop"]: sounds["power_loop"].stop() # Para sirene
                if sounds["gameover"]: sounds["gameover"].play()

        # Atualiza estados anteriores
        last_power_active = power_active
        last_lives = lives
        last_score = score
        last_game_over = game_over

        # ---------------------------------------------------------

        # 3. Desenhar Objetos
        for obj in objetos:
            nome = obj.get("personagem", "")
            try:
                mx = int(obj['x_global'] * SCALE_FACTOR) + X_OFFSET
                my = int(obj['y_global'] * SCALE_FACTOR) + Y_OFFSET
                ang = float(obj['angulo_graus'])
            except: continue

            if 'pac-man' in nome:
                draw_pacman(screen, mx, my, 25, ang, power_active)
                if immunity: 
                    pygame.draw.circle(screen, (255, 255, 255), (mx, my), 30, 2)
            elif 'fantasma' in nome:
                color = COLOR_FANTASMA_VULNERAVEL if power_active else COLOR_FANTASMA
                draw_rotated_rect(screen, color, mx, my, 40, 40, ang)
            
            lbl = font_main.render(f"{nome}", True, COLOR_TEXTO)
            screen.blit(lbl, (mx+20, my-20))

        # 4. HUD
        mins, secs = divmod(int(time_rem), 60)
        timer_str = f"{mins:02}:{secs:02}"
        color_time = (255, 0, 0) if time_rem < 30 else (255, 255, 255)
        
        hud_timer = font_hud.render(f"TEMPO: {timer_str}", True, color_time)
        hud_score = font_hud.render(f"PONTOS: {score}", True, (0, 255, 0))
        hud_lives = font_hud.render(f"VIDAS: {lives}", True, (0, 0, 255))
        
        screen.blit(hud_timer, (20, 20))
        screen.blit(hud_score, (300, 20))
        screen.blit(hud_lives, (600, 20))
        
        if power_active:
            p_surf = font_main.render(f"CAÇADOR: {estado.get('power_timer',0)}s", True, COLOR_PACMAN_HUNTER)
            screen.blit(p_surf, (20, 60))
        if estado.get("speed_active"):
            s_surf = font_main.render(f"SPEED: {estado.get('speed_timer',0)}s", True, (0, 255, 255))
            screen.blit(s_surf, (20, 85))

        # 5. Overlays
        if game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180)) 
            screen.blit(overlay, (0,0))
            go_text = font_big.render("GAME OVER", True, (255, 0, 0))
            final_score = font_hud.render(f"PONTUAÇÃO FINAL: {score}", True, (255, 255, 255))
            
            rect_go = go_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50))
            rect_sc = final_score.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 20))
            screen.blit(go_text, rect_go)
            screen.blit(final_score, rect_sc)
            
        elif paused:
            msg = font_big.render("PAUSADO", True, (255, 255, 0))
            sub = font_hud.render("Aguardando Servidor ou Tecla ESPAÇO...", True, (200, 200, 200))
            rect_msg = msg.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
            rect_sub = sub.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 60))
            screen.blit(msg, rect_msg)
            screen.blit(sub, rect_sub)

        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == "__main__":
    ws_t = start_ws_thread()
    try: pygame_loop()
    except Exception as e: print(e)
    finally: sys.exit()

    
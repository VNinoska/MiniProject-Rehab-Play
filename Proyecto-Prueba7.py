import cv2
import mediapipe as mp
import random
import time
import math
import numpy as np
import pygame

mp_hands = mp.solutions.hands

# =========================
#  CONFIGURACIONES JUEGO
# =========================
ARCO_DURACION = 2.0       # Tiempo límite para bolas con gusanito
SLIDER_TIEMPO = 3.0       # Tiempo total para recorrer el slider
SLIDER_RADIO = 100        # Radio del arco del slider
SLIDER_ANGULO = 120       # Amplitud del arco en grados
SLIDER_PUNTOS = 20        # Cantidad de círculos en el slider
SLIDER_TOLERANCIA_INICIO = 10  # Puntos iniciales donde se puede enganchar
SEGUIR_RANGO = 40         # Distancia máxima para seguir activo

# Tipos de bola
TIPO_NORMAL = 0
TIPO_ARCO_TIMER = 1
TIPO_SLIDER = 2

# =========================
#   ESTADOS DE LA APP
# =========================
STATE_MENU = "menu"
STATE_CONFIG = "config"
STATE_GAME = "game"
STATE_EXIT = "exit"

# Resoluciones disponibles (ancho, alto)
RESOLUCIONES = [
    (640, 480),
    (1280, 720),
    (1920, 1080),
]

# Selección por defecto
res_index = 0  # 640x480

# =========================
#  UI con OpenCV (botones)
# =========================
class Boton:
    def __init__(self, x, y, w, h, texto, color=(255, 255, 255), color_texto=(0, 0, 0), grosor=2):
        self.rect = (x, y, w, h)
        self.texto = texto
        self.color = color
        self.color_texto = color_texto
        self.grosor = grosor

    def draw(self, img):
        x, y, w, h = self.rect
        cv2.rectangle(img, (x, y), (x + w, y + h), self.color, -1)
        cv2.rectangle(img, (x, y), (x + w, y + h), (50, 50, 50), 2)
        # Texto centrado
        (tw, th), _ = cv2.getTextSize(self.texto, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        tx = x + (w - tw) // 2
        ty = y + (h + th) // 2
        cv2.putText(img, self.texto, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.9, self.color_texto, 2)

    def is_over(self, mx, my):
        x, y, w, h = self.rect
        return (x <= mx <= x + w) and (y <= my <= y + h)

# Variables del mouse para menús
mouse_pos = (0, 0)
mouse_clicked = False

def mouse_callback(event, x, y, flags, param):
    global mouse_pos, mouse_clicked
    mouse_pos = (x, y)
    if event == cv2.EVENT_LBUTTONDOWN:
        mouse_clicked = True

# =========================
#    LÓGICA DEL JUEGO
# =========================

MARGEN_SUPERIOR = 80  # pixeles de zona prohibida arriba

def spawn_ball(w, h, radius=20):
    tipo = random.choices(
        [TIPO_NORMAL, TIPO_ARCO_TIMER, TIPO_SLIDER],
        weights=[0.4, 0.4, 0.2]
    )[0]

    if tipo == TIPO_SLIDER:
        cx = random.randint(radius + SLIDER_RADIO + 20, w - SLIDER_RADIO - radius - 20)
        cy = random.randint(MARGEN_SUPERIOR + radius + SLIDER_RADIO + 20, h - SLIDER_RADIO - radius - 20)
        ang_ini = random.randint(0, 360 - SLIDER_ANGULO)
        ang_fin = ang_ini + SLIDER_ANGULO

        # Generar puntos del arco
        puntos = []
        for i in range(SLIDER_PUNTOS):
            t = i / (SLIDER_PUNTOS - 1)
            ang = math.radians(ang_ini + (ang_fin - ang_ini) * t)
            x = int(cx + SLIDER_RADIO * math.cos(ang))
            y = int(cy + SLIDER_RADIO * math.sin(ang))
            puntos.append((x, y))

        return {
            "tipo": tipo,
            "radius": radius,
            "spawn_time": time.time(),
            "puntos": puntos,
            "indice": 0,
            "siguiendo": False,
            "fallo": False
        }

    elif tipo == TIPO_ARCO_TIMER:
        return {
            "tipo": tipo,
            "pos": (random.randint(radius, w - radius), random.randint(MARGEN_SUPERIOR + radius, h - radius)),
            "radius": radius,
            "spawn_time": time.time()
        }

    else:
        return {
            "tipo": tipo,
            "pos": (random.randint(MARGEN_SUPERIOR + radius, w - radius), random.randint(radius, h - radius)),
            "radius": radius
        }

def run_game(cam_w, cam_h):
    # =========================
    #     AUDIO (opcional)
    # =========================
    try:
        pygame.mixer.init()
        pygame.mixer.music.load("Action - Daiki Yamashita (1).mp3")
        pygame.mixer.music.play(-1)
    except Exception as e:
        print("Aviso: no se pudo iniciar el audio:", e)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No se pudo abrir la cámara.")
        return

    # Intentar aplicar resolución seleccionada
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_h)

    balls = []
    score = 0
    last_spawn = time.time()
    spawn_interval = 1.5
    paused = False

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5) as hands:

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            height, width, _ = frame.shape
            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(frame_rgb)

            palmas = []
            if results.multi_hand_landmarks:
                puntos_track = [1, 5, 9, 13, 17]
                for hand_landmarks in results.multi_hand_landmarks:
                    for i, lm in enumerate(hand_landmarks.landmark):
                        if i in puntos_track:
                            x = int(lm.x * width)
                            y = int(lm.y * height)
                            palmas.append((x, y))
                            cv2.circle(frame, (x, y), 4, (255, 0, 0), -1)

            now = time.time()

            if not paused and now - last_spawn >= spawn_interval:
                nueva_bola = spawn_ball(width, height, radius=20)
                balls.append(nueva_bola)

                # Ajustar intervalo según tipo
                if nueva_bola["tipo"] == TIPO_SLIDER:
                    spawn_interval = SLIDER_TIEMPO * 1.0  #espera más tiempo cuando aparece el slider
                else:
                    spawn_interval = 1.5  # valor normal
                
                last_spawn= now

            for ball in balls[:]:
                br = ball["radius"]

                # --- SLIDER ---
                if ball["tipo"] == TIPO_SLIDER:
                    elapsed = now - ball["spawn_time"]
                    t = elapsed / SLIDER_TIEMPO
                    if t >= 1.0:
                        if ball["siguiendo"] and not ball["fallo"]:
                            score += 1
                        balls.remove(ball)
                        continue

                    indice_actual = int(t * (SLIDER_PUNTOS - 1))
                    indice_actual = min(indice_actual, SLIDER_PUNTOS - 1)
                    ball["indice"] = indice_actual

                    # Dibujar solo puntos no recorridos
                    for i in range(indice_actual, SLIDER_PUNTOS):
                        px, py = ball["puntos"][i]
                        cv2.circle(frame, (px, py), br, (100, 255, 100), 2)

                    # Bola activa
                    bx, by = ball["puntos"][indice_actual]
                    cv2.circle(frame, (bx, by), br, (0, 255, 0), -1)

                    # Verificar rango
                    en_rango = any(math.dist((bx, by), (hx, hy)) <= SEGUIR_RANGO for hx, hy in palmas)

                    if indice_actual < SLIDER_TOLERANCIA_INICIO and en_rango:
                        ball["siguiendo"] = True
                    elif ball["siguiendo"] and not en_rango:
                        ball["fallo"] = True

                # --- ARCO TIMER ---
                elif ball["tipo"] == TIPO_ARCO_TIMER:
                    bx, by = ball["pos"]
                    cv2.circle(frame, (bx, by), br, (0, 165, 255), -1)
                    elapsed = now - ball["spawn_time"]
                    progreso = min(elapsed / ARCO_DURACION, 1.0)
                    angulo_final = int(progreso * 360)
                    cv2.ellipse(frame, (bx, by), (br+15, br+15), 0, 0, angulo_final, (255, 255, 255), 3)
                    if elapsed >= ARCO_DURACION:
                        balls.remove(ball)
                        continue
                    if any(math.dist((bx, by), (px, py)) <= br + 10 for px, py in palmas):
                        balls.remove(ball)
                        score += 1

                # --- NORMAL ---
                else:
                    bx, by = ball["pos"]
                    cv2.circle(frame, (bx, by), br, (255, 0, 255), -1)
                    if any(math.dist((bx, by), (px, py)) <= br + 10 for px, py in palmas):
                        balls.remove(ball)
                        score += 1

            if len(balls) >= 3 and not paused:
                paused = True

            if paused:
                cv2.putText(frame, "Pausado por inactividad - Perdiste", (50, height//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                cv2.putText(frame, "Presiona ESPACIO para reiniciar", (50, height//2 + 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                pygame.mixer.music.stop()
            
            cv2.putText(frame, f"Puntaje: {score}", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 3)
            cv2.putText(frame, f"Bolas: {len(balls)}", (width-150, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            cv2.putText(frame, "Pon la palma sobre las pelotas para sumar puntos", (10, height-15), #mensaje que aparece en pantalla, pueden cambiar 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

            cv2.imshow("Osu-Replica [Presiona \"Esc\" para salir]", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC para salir del juego a menú
                pygame.mixer.music.stop()
                break
            if key == 32 and paused:  # SPACE para reiniciar
                balls.clear()
                score = 0
                paused = False
                last_spawn = time.time()
                pygame.mixer.music.play(-1)

    cap.release()
    cv2.destroyAllWindows()

# =========================
#  PANTALLAS DE MENÚ/CONFIG
# =========================
def draw_menu():
    """Devuelve una imagen con el menú principal."""
    h, w = 600, 900
    img = np.full((h, w, 3), (235, 247, 255), dtype=np.uint8)  # azul muy claro
    # Título
    cv2.putText(img, "OSU! Replica - Vision", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (70, 90, 130), 5)
    cv2.putText(img, "OSU! Replica - Vision", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 2)

    # Subtítulo
    cv2.putText(img, "Usa tu mano para tocar las bolas y sliders", (80, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (60, 80, 120), 2)

    return img

def draw_config(selected_idx):
    """Devuelve una imagen con la pantalla de configuracion."""
    h, w = 600, 900
    img = np.full((h, w, 3), (235, 247, 255), dtype=np.uint8)  # azul muy claro

    cv2.putText(img, "Configuracion de Camara", (80, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (70, 90, 130), 5)
    cv2.putText(img, "Configuracion de Camara", (80, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 2)

    cv2.putText(img, "Selecciona la resolucion de captura:", (80, 160),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (60, 80, 120), 2)

    # Mostrar opciones
    y0 = 210
    gap = 70
    for i, (rw, rh) in enumerate(RESOLUCIONES):
        texto = f"{rw} x {rh}"
        color_box = (255, 255, 255) if i != selected_idx else (180, 220, 255)
        cv2.rectangle(img, (90, y0 + i * gap - 35), (370, y0 + i * gap + 5), color_box, -1)
        cv2.rectangle(img, (90, y0 + i * gap - 35), (370, y0 + i * gap + 5), (50, 50, 50), 2)
        cv2.putText(img, texto, (110, y0 + i * gap), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2)

    cv2.putText(img, "La resolucion se aplicara al iniciar el juego.", (80, 420),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 80, 120), 2)

    return img

def main():
    global mouse_clicked, res_index

    estado = STATE_MENU

    # Crear ventana de UI y registrar callback del mouse
    cv2.namedWindow("OSU - Menu", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("OSU - Menu", mouse_callback)

    # Botones en menú principal
    btn_iniciar = Boton(330, 250, 240, 60, "Iniciar", color=(255, 255, 255))
    btn_config = Boton(330, 330, 240, 60, "Configurar", color=(255, 255, 255))
    btn_salir  = Boton(330, 410, 240, 60, "Salir", color=(255, 255, 255))

    # Botones en configuración
    # Cada opción de resolución también será clickeable
    # Además, botones "Volver" e "Iniciar"
    btn_cfg_volver = Boton(90, 480, 200, 55, "Volver", color=(255, 255, 255))
    btn_cfg_iniciar = Boton(610, 480, 200, 55, "Iniciar", color=(255, 255, 255))

    while True:
        if estado == STATE_MENU:
            img = draw_menu()
            # Dibujar botones
            btn_iniciar.draw(img)
            btn_config.draw(img)
            btn_salir.draw(img)

            # Sombra al pasar el mouse (opcional)
            mx, my = mouse_pos
            for b in [btn_iniciar, btn_config, btn_salir]:
                if b.is_over(mx, my):
                    x, y, w, h = b.rect
                    cv2.rectangle(img, (x, y), (x + w, y + h), (210, 230, 255), 2)

            cv2.imshow("OSU - Menu", img)
            key = cv2.waitKey(20) & 0xFF

            if key == 27:  # ESC
                estado = STATE_EXIT

            if mouse_clicked:
                mouse_clicked = False
                if btn_iniciar.is_over(mx, my):
                    # Ir al juego con la resolución seleccionada
                    cv2.destroyWindow("OSU - Menu")
                    w, h = RESOLUCIONES[res_index]
                    run_game(w, h)
                    # Volver al menú al terminar el juego
                    cv2.namedWindow("OSU - Menu", cv2.WINDOW_AUTOSIZE)
                    cv2.setMouseCallback("OSU - Menu", mouse_callback)
                elif btn_config.is_over(mx, my):
                    estado = STATE_CONFIG
                elif btn_salir.is_over(mx, my):
                    estado = STATE_EXIT

        elif estado == STATE_CONFIG:
            img = draw_config(res_index)

            # Dibujar botones
            btn_cfg_volver.draw(img)
            btn_cfg_iniciar.draw(img)

            # Dibujar cajas clickeables para resoluciones
            y0 = 210
            gap = 70
            res_boxes = []
            for i, (rw, rh) in enumerate(RESOLUCIONES):
                box = (90, y0 + i * gap - 35, 280, 40)  # x, y, w, h
                res_boxes.append((box, i))
                # resaltado al pasar el mouse
                mx, my = mouse_pos
                x, y, w, h = box
                if (x <= mx <= x + w) and (y <= my <= y + h):
                    cv2.rectangle(img, (x, y), (x + w, y + h), (210, 230, 255), 2)

            cv2.imshow("OSU - Menu", img)
            key = cv2.waitKey(20) & 0xFF

            if key == 27:  # ESC
                estado = STATE_MENU

            if mouse_clicked:
                mx, my = mouse_pos
                mouse_clicked = False
                # Click en resolución
                for (x, y, w, h), idx in res_boxes:
                    if (x <= mx <= x + w) and (y <= my <= y + h):
                        res_index = idx
                        break
                # Click en botones
                if btn_cfg_volver.is_over(mx, my):
                    estado = STATE_MENU
                elif btn_cfg_iniciar.is_over(mx, my):
                    # Iniciar juego con resolución seleccionada
                    cv2.destroyWindow("OSU - Menu")
                    w, h = RESOLUCIONES[res_index]
                    run_game(w, h)
                    # Al salir del juego, volver a abrir la ventana de menú
                    cv2.namedWindow("OSU - Menu", cv2.WINDOW_AUTOSIZE)
                    cv2.setMouseCallback("OSU - Menu", mouse_callback)

        elif estado == STATE_EXIT:
            break

    try:
        cv2.destroyAllWindows()
    except:
        pass

if __name__ == "__main__":
    main()


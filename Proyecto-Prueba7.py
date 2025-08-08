import cv2
import mediapipe as mp
import random
import time
import math

import pygame  # <-- añadido

# Inicializar y reproducir música
pygame.mixer.init()
pygame.mixer.music.load("Pharrell Williams - Happy.mp3")
pygame.mixer.music.play(-1)


mp_hands = mp.solutions.hands

# Configuración
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

def spawn_ball(w, h, radius=20):
    tipo = random.choices(
        [TIPO_NORMAL, TIPO_ARCO_TIMER, TIPO_SLIDER],
        weights=[0.4, 0.4, 0.2]
    )[0]

    if tipo == TIPO_SLIDER:
        cx = random.randint(radius + SLIDER_RADIO + 20, w - SLIDER_RADIO - radius - 20)
        cy = random.randint(radius + SLIDER_RADIO + 20, h - SLIDER_RADIO - radius - 20)
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
            "pos": (random.randint(radius, w - radius), random.randint(radius, h - radius)),
            "radius": radius,
            "spawn_time": time.time()
        }

    else:
        return {
            "tipo": tipo,
            "pos": (random.randint(radius, w - radius), random.randint(radius, h - radius)),
            "radius": radius
        }

def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("No se pudo abrir la cámara.")
        return

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
                balls.append(spawn_ball(width, height, radius=20))
                last_spawn = now

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
            if key == 27:
                break
            if key == 32 and paused:
                balls.clear()
                score = 0
                paused = False
                last_spawn = time.time()
                pygame.mixer.music.play(-1)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

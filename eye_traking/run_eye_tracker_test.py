import argparse
import time

import cv2

from eye_traker import EyeDetector
from keyboard_logic import KeyboardBrain  # <-- Importamos tu nuevo cerebro lógico


def draw_overlay(frame, data, fps, estado_teclado):
    gaze = data.get("gaze") or "NO_FACE"
    blink = "YES" if data.get("blink") else "NO"

    # 1. Textos originales de la cámara
    cv2.putText(frame, f"GAZE: {gaze}", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)

    cv2.putText(frame, f"BLINK: {blink}", (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)

    cv2.putText(frame, f"FPS: {fps:.1f}", (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2, cv2.LINE_AA)

    # 2. NUEVO: Textos de tu lógica de teclado
    current_key = estado_teclado["current_key"]
    cv2.putText(frame, f"TECLA ACTUAL: {current_key}", (20, 150),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2, cv2.LINE_AA)

    # Aviso visual rápido cuando parpadeas
    if estado_teclado["is_clicking"]:
        cv2.putText(frame, f"ESCRIBIENDO: {estado_teclado['typed_key']}", (20, 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3, cv2.LINE_AA)

    # 3. Dibujar las pupilas
    for pupil in data.get("pupils", []):
        cv2.circle(frame, pupil, 4, (0, 0, 255), -1)


def main():
    parser = argparse.ArgumentParser(description="Real-time eye tracking test")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    args = parser.parse_args()

    # Instanciamos tus dos clases maestras
    detector = EyeDetector()
    brain = KeyboardBrain()  # <-- Creamos la instancia de la lógica
    
    cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        raise RuntimeError(
            f"No se pudo abrir la camara con indice {args.camera}. "
            "Prueba con --camera 1 o revisa permisos."
        )

    print("==================================================")
    print("🚀 INICIANDO PRUEBA DEL BACKEND LÓGICO")
    print("Mueve los ojos para navegar y parpadea para teclear.")
    print("Revisa esta consola para ver los paquetes enviados al frontend.")
    print("==================================================")

    prev_time = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("No se pudo leer un frame de la camara.")
                break

            frame = cv2.flip(frame, 1)
            
            # Paso A: El detector saca los datos crudos
            data = detector.process_frame(frame)

            # Paso B: El cerebro convierte esos datos en comandos de teclado
            estado_teclado = brain.update_state(data["gaze"], data["blink"])

            # Paso C: La prueba de fuego en la consola
            if estado_teclado["is_clicking"]:
                hora = time.strftime('%H:%M:%S')
                print(f"[{hora}] ¡PAQUETE LISTO! Letra enviada al frontend -> {estado_teclado['typed_key']}")

            # Calcular FPS
            current_time = time.time()
            delta = max(current_time - prev_time, 1e-6)
            fps = 1.0 / delta
            prev_time = current_time

            # Dibujar todo en pantalla
            draw_overlay(frame, data, fps, estado_teclado)

            cv2.imshow("Eye Tracker Test", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
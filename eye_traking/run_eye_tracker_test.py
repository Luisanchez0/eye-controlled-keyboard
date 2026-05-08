import argparse
from dataclasses import dataclass
import time
import threading
import queue

import cv2
import os
import sys

# Ensure project root is on sys.path so sibling packages like `front_keyboard` are importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eye_traker import EyeDetector
from keyboard_logic import KeyboardBrain  # <-- Importamos tu nuevo cerebro lógico
from front_keyboard.desktop_keyboard import DesktopKeyboardApp


@dataclass
class CameraState:
    thread: threading.Thread | None = None
    stop_event: threading.Event | None = None
    camera_index: int | None = None


def discover_cameras(max_index=10):
    available = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
        if cap.isOpened():
            available.append(idx)
        cap.release()
    return available


def put_latest(out_queue, packet):
    try:
        out_queue.put_nowait(packet)
    except queue.Full:
        try:
            out_queue.get_nowait()
        except queue.Empty:
            pass
        out_queue.put_nowait(packet)


def camera_loop(camera_index, out_queue, stop_event):
    detector = EyeDetector()
    cap = cv2.VideoCapture(camera_index, cv2.CAP_ANY)
    if not cap.isOpened():
        put_latest(out_queue, {"error": f"No se pudo abrir la camara con indice {camera_index}", "camera_index": camera_index})
        return

    prev_time = time.time()
    preview_warned = False

    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                put_latest(out_queue, {"error": "No se pudo leer un frame de la camara.", "camera_index": camera_index})
                break

            frame = cv2.flip(frame, 1)

            data = detector.process_frame(frame)

            # Normalizar pupilas (0..1) para el frontend
            pupils = []
            h, w, _ = frame.shape
            if h <= 0 or w <= 0:
                put_latest(
                    out_queue,
                    {"error": "Frame invalido recibido de la camara (dimensiones no validas).", "camera_index": camera_index},
                )
                break
            for (x, y) in data.get("pupils", []):
                pupils.append((x / w, y / h))

            # Calcular FPS (opcional)
            current_time = time.time()
            delta = max(current_time - prev_time, 1e-6)
            fps = 1.0 / delta
            prev_time = current_time

            # Draw pupil markers on preview frame
            frame_with_overlay = frame.copy()
            for (x, y) in data.get("pupils", []):
                cv2.circle(frame_with_overlay, (int(x), int(y)), 8, (0, 255, 0), 2)
                cv2.circle(frame_with_overlay, (int(x), int(y)), 2, (0, 255, 0), -1)

            # Small RGB preview frame for frontend (resized)
            try:
                frame_preview = cv2.resize(cv2.cvtColor(frame_with_overlay, cv2.COLOR_BGR2RGB), (320, 240))
            except cv2.error as exc:
                if not preview_warned:
                    print(f"WARN: no se pudo generar preview RGB: {exc}")
                    preview_warned = True
                frame_preview = None

            packet = {
                "gaze": data.get("gaze"),
                "gaze_point": data.get("gaze_point"),
                "head_point": data.get("head_point"),
                "blink": data.get("blink", False),
                "face_detected": data.get("face_detected", False),
                "pupils": pupils,
                "fps": fps,
                "frame_rgb": frame_preview,
                "camera_index": camera_index,
            }

            # Enviar al frontend
            put_latest(out_queue, packet)

            # Pequeña pausa para evitar sobrecarga
            time.sleep(0.01)
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description="Real-time eye tracking desktop demo")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument(
        "--control-mode",
        choices=("gaze", "head"),
        default="head",
        help="Control keyboard using continuous head movement (default) or eye gaze direction (gaze)",
    )
    args = parser.parse_args()

    brain = KeyboardBrain()

    q = queue.Queue(maxsize=1)
    camera_state = CameraState()

    # Start desktop GUI in main thread
    app = DesktopKeyboardApp(brain.keys)
    app.set_control_mode(args.control_mode)
    discovered = discover_cameras(max_index=10)
    if args.camera not in discovered:
        discovered = [args.camera] + discovered
    app.set_camera_options(discovered, selected_index=args.camera)

    def drain_queue():
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break

    def stop_camera():
        stop_evt = camera_state.stop_event
        cam_thread = camera_state.thread
        if stop_evt is not None:
            stop_evt.set()
        if cam_thread is not None and cam_thread.is_alive():
            cam_thread.join(timeout=0.1)
        camera_state.thread = None
        camera_state.stop_event = None

    def start_camera(camera_index):
        stop_camera()
        drain_queue()
        stop_event = threading.Event()
        cam_thread = threading.Thread(target=camera_loop, args=(camera_index, q, stop_event), daemon=True)
        camera_state.camera_index = camera_index
        camera_state.stop_event = stop_event
        camera_state.thread = cam_thread
        app.set_camera_status(f"Camara activa: {camera_index}")
        cam_thread.start()

    def on_camera_change(camera_index):
        if camera_index == camera_state.camera_index:
            return
        print(f"INFO: cambiando a camara {camera_index}")
        start_camera(camera_index)

    app.set_on_camera_change(on_camera_change)
    start_camera(args.camera)

    def poll():
        while True:
            try:
                pkt = q.get_nowait()
            except queue.Empty:
                break
            packet_camera = pkt.get("camera_index")
            if packet_camera is not None and packet_camera != camera_state.camera_index:
                continue
            if "error" in pkt:
                error_msg = pkt["error"]
                print("ERROR:", error_msg)
                app.show_error(error_msg)
                app.set_camera_status(f"Camara con error: {camera_state.camera_index}")
                continue

            pupils = pkt.get("pupils", [])
            frame = pkt.get("frame_rgb")
            gaze_point = pkt.get("gaze_point")
            head_point = pkt.get("head_point")
            control_point = head_point if args.control_mode == "head" else gaze_point
            if control_point is None:
                control_point = gaze_point if args.control_mode == "head" else head_point
            tuning = app.get_runtime_tuning()
            brain.set_tuning(
                move_cooldown=tuning["move_cooldown"],
                blink_cooldown=tuning["blink_cooldown"],
            )
            calibrated_gaze = app.classify_gaze(
                control_point,
                allow_uncalibrated=(args.control_mode == "head"),
            )
            gaze = calibrated_gaze or pkt.get("gaze")
            estado = brain.update_state(gaze, pkt.get("blink", False))
            app.update_state(
                estado,
                pupils,
                gaze_point=gaze_point,
                control_point=control_point,
                frame_rgb=frame,
                use_cursor_selection=(args.control_mode == "head"),
            )

            if estado.get("is_clicking"):
                hora = time.strftime('%H:%M:%S')
                print(f"[{hora}] Letra enviada: {estado.get('typed_key')}")

    def on_close():
        stop_camera()

    app.set_on_close(on_close)
    app.mainloop(poll_callback=poll, poll_interval=33)


if __name__ == "__main__":
    main()

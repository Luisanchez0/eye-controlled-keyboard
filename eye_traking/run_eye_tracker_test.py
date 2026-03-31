import argparse
import time

import cv2

from eye_traker import EyeDetector


def draw_overlay(frame, data, fps):
    gaze = data.get("gaze") or "NO_FACE"
    blink = "YES" if data.get("blink") else "NO"

    cv2.putText(
        frame,
        f"GAZE: {gaze}",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        f"BLINK: {blink}",
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (20, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 0),
        2,
        cv2.LINE_AA,
    )

    for pupil in data.get("pupils", []):
        cv2.circle(frame, pupil, 4, (0, 0, 255), -1)


def main():
    parser = argparse.ArgumentParser(description="Real-time eye tracking test")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    args = parser.parse_args()

    detector = EyeDetector()
    cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        raise RuntimeError(
            f"No se pudo abrir la camara con indice {args.camera}. "
            "Prueba con --camera 1 o revisa permisos."
        )

    prev_time = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("No se pudo leer un frame de la camara.")
                break

            frame = cv2.flip(frame, 1)
            data = detector.process_frame(frame)

            current_time = time.time()
            delta = max(current_time - prev_time, 1e-6)
            fps = 1.0 / delta
            prev_time = current_time

            draw_overlay(frame, data, fps)

            cv2.imshow("Eye Tracker Test", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

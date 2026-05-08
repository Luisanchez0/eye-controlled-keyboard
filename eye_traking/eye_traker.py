import cv2
from mediapipe.python.solutions import face_mesh as mp_face_mesh


class EyeDetector:
    def __init__(self):
        self.mp_face_mesh = mp_face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # Bug 3 fix: confirmación de parpadeo por frames consecutivos
        self._blink_counter = 0
        self._blink_frames_needed = 2

        # Bug 4 fix: buffer para suavizar el gaze_point
        self._gaze_buffer = []
        self._gaze_buffer_size = 7

    def _eye_ratio(self, landmarks, left_idx, right_idx, top_idx, bottom_idx, pupil_idx):
        left = landmarks[left_idx]
        right = landmarks[right_idx]
        top = landmarks[top_idx]
        bottom = landmarks[bottom_idx]
        pupil = landmarks[pupil_idx]

        min_x = min(left.x, right.x)
        max_x = max(left.x, right.x)
        eye_width = max_x - min_x
        if abs(eye_width) < 1e-6:
            return None
        x_ratio = (pupil.x - min_x) / eye_width

        eye_height = bottom.y - top.y
        if abs(eye_height) < 1e-6:
            return None
        y_ratio = (pupil.y - top.y) / eye_height

        return x_ratio, y_ratio

    def _get_gaze_direction(self, landmarks, gaze_point=None):
        if gaze_point is None:
            gaze_point = self._get_gaze_point(landmarks)
        if gaze_point is None:
            return "CENTER"

        x_ratio, y_ratio = gaze_point

        # Bug 1 fix: umbrales más amplios para que CENTER no capture todo
        if x_ratio < 0.38:
            return "LEFT"
        if x_ratio > 0.62:
            return "RIGHT"
        if y_ratio < 0.35:
            return "UP"
        if y_ratio > 0.65:
            return "DOWN"
        return "CENTER"

    def _get_gaze_point(self, landmarks):
        left_eye = self._eye_ratio(landmarks, 33, 133, 159, 145, 468)
        right_eye = self._eye_ratio(landmarks, 362, 263, 386, 374, 473)

        ratios = [ratio for ratio in (left_eye, right_eye) if ratio is not None]
        if not ratios:
            return None

        x_ratio = sum(ratio[0] for ratio in ratios) / len(ratios)
        y_ratio = sum(ratio[1] for ratio in ratios) / len(ratios)

        # Bug 4 fix: suavizado con promedio móvil para reducir jitter
        self._gaze_buffer.append((x_ratio, y_ratio))
        if len(self._gaze_buffer) > self._gaze_buffer_size:
            self._gaze_buffer.pop(0)

        sx = sum(p[0] for p in self._gaze_buffer) / len(self._gaze_buffer)
        sy = sum(p[1] for p in self._gaze_buffer) / len(self._gaze_buffer)
        return sx, sy

    def _eye_aspect_ratio(self, landmarks, left_idx, right_idx, top_idx, bottom_idx):
        top = landmarks[top_idx]
        bottom = landmarks[bottom_idx]
        left = landmarks[left_idx]
        right = landmarks[right_idx]

        vertical = abs(top.y - bottom.y)
        horizontal = abs(left.x - right.x)
        if horizontal < 1e-6:
            return None
        return vertical / horizontal

    def _is_blinking(self, landmarks):
        # Bug 2 fix: índices correctos de MediaPipe para apertura de párpados
        # Ojo izquierdo: top=160, bottom=144  (antes: 159/145)
        # Ojo derecho:   top=385, bottom=373  (antes: 386/374)
        ratios = [
            self._eye_aspect_ratio(landmarks, 33, 133, 160, 144),
            self._eye_aspect_ratio(landmarks, 362, 263, 385, 373),
        ]
        ratios = [ratio for ratio in ratios if ratio is not None]
        if not ratios:
            self._blink_counter = 0
            return False

        ear = sum(ratios) / len(ratios)

        # Bug 3 fix: umbral más estricto (0.15) + confirmación por N frames
        if ear < 0.15:
            self._blink_counter += 1
        else:
            self._blink_counter = 0

        # Solo se considera parpadeo al llegar exactamente al frame requerido
        # (evita disparar True en cada frame mientras el ojo sigue cerrado)
        return self._blink_counter == self._blink_frames_needed

    def process_frame(self, frame):
        """
        Entrada: frame (BGR)
        Salida: dict con info de ojos
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        data = {
            "gaze": None,
            "gaze_point": None,
            "head_point": None,
            "blink": False,
            "pupils": [],
            "face_detected": False,
        }

        multi_face_landmarks = getattr(results, "multi_face_landmarks", None)
        if multi_face_landmarks:
            data["face_detected"] = True
            face_landmarks = multi_face_landmarks[0]
            landmarks = face_landmarks.landmark

            gaze_point = self._get_gaze_point(landmarks)
            data["gaze_point"] = gaze_point
            data["gaze"] = self._get_gaze_direction(landmarks, gaze_point=gaze_point)
            data["blink"] = self._is_blinking(landmarks)

            xs = [landmark.x for landmark in landmarks]
            ys = [landmark.y for landmark in landmarks]
            if xs and ys:
                data["head_point"] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

            h, w, _ = frame.shape
            for idx in [468, 473]:
                x = int(landmarks[idx].x * w)
                y = int(landmarks[idx].y * h)
                data["pupils"].append((x, y))

        return data

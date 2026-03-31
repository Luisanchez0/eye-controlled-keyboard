import cv2
from mediapipe.python.solutions import face_mesh as mp_face_mesh

class EyeDetector:
    def __init__(self):
        self.mp_face_mesh = mp_face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(refine_landmarks=True)

    def _get_gaze_direction(self, landmarks):
        # Ojo izquierdo
        left_eye_left = landmarks[33]
        left_eye_right = landmarks[133]
        left_pupil = landmarks[468]

        eye_width = left_eye_right.x - left_eye_left.x
        if abs(eye_width) < 1e-6:
            return "CENTER"
        pupil_pos = (left_pupil.x - left_eye_left.x) / eye_width

        if pupil_pos < 0.35:
            return "LEFT"
        elif pupil_pos > 0.65:
            return "RIGHT"
        else:
            return "CENTER"

    def _is_blinking(self, landmarks):
        top = landmarks[159]
        bottom = landmarks[145]

        eye_distance = abs(top.y - bottom.y)

        return eye_distance < 0.01

    def process_frame(self, frame):
        """
        Entrada: frame (BGR)
        Salida: dict con info de ojos
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        data = {
            "gaze": None,
            "blink": False,
            "pupils": []
        }

        multi_face_landmarks = getattr(results, "multi_face_landmarks", None)
        if multi_face_landmarks:
            face_landmarks = multi_face_landmarks[0]
            landmarks = face_landmarks.landmark

            # Dirección de mirada
            data["gaze"] = self._get_gaze_direction(landmarks)

            # Parpadeo
            data["blink"] = self._is_blinking(landmarks)

            # Coordenadas de pupilas
            h, w, _ = frame.shape
            for idx in [468, 473]:
                x = int(landmarks[idx].x * w)
                y = int(landmarks[idx].y * h)
                data["pupils"].append((x, y))

        return data
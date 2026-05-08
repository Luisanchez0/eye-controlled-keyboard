import time
from collections import Counter, deque


class KeyboardBrain:
    def __init__(self):
        self.keys = [
            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'Ñ'],
            ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '-'],
            ['SPACE', 'BACKSPACE', 'ENTER']
        ]
        self.row = 1
        self.col = 4

        self.history_size = 5
        self.min_stable_samples = 3
        self.gaze_history = deque(maxlen=self.history_size)

        self.last_move_time = time.time()
        self.move_cooldown = 1.0

        self.last_blink_time = time.time()
        self.blink_cooldown = 1.0

    def set_tuning(self, move_cooldown=None, blink_cooldown=None):
        if move_cooldown is not None:
            self.move_cooldown = max(0.05, float(move_cooldown))
        if blink_cooldown is not None:
            self.blink_cooldown = max(0.05, float(blink_cooldown))

    def _clamp_cursor(self):
        self.row = max(0, min(self.row, len(self.keys) - 1))
        self.col = max(0, min(self.col, len(self.keys[self.row]) - 1))

    def _stable_gaze(self):
        if not self.gaze_history:
            return "CENTER"

        gaze, count = Counter(self.gaze_history).most_common(1)[0]
        if gaze in ("LEFT", "RIGHT", "UP", "DOWN") and count >= self.min_stable_samples:
            return gaze
        return "CENTER"

    def update_state(self, gaze_direction, is_blinking):
        current_time = time.time()
        moved = False
        click_triggered = False
        selected_key = None

        if gaze_direction in ("LEFT", "RIGHT", "UP", "DOWN", "CENTER"):
            self.gaze_history.append(gaze_direction)

        stable_gaze = self._stable_gaze()

        if current_time - self.last_move_time > self.move_cooldown:
            if stable_gaze == "RIGHT":
                self.col += 1
                moved = True
            elif stable_gaze == "LEFT":
                self.col -= 1
                moved = True
            elif stable_gaze == "DOWN":
                self.row += 1
                moved = True
            elif stable_gaze == "UP":
                self.row -= 1
                moved = True

            if moved:
                self.gaze_history.clear()
                self.last_move_time = current_time

        self._clamp_cursor()
        current_key = self.keys[self.row][self.col]

        if is_blinking and (current_time - self.last_blink_time > self.blink_cooldown):
            click_triggered = True
            selected_key = current_key
            self.last_blink_time = current_time

        return {
            "cursor_row": self.row,
            "cursor_col": self.col,
            "current_key": current_key,
            "is_clicking": click_triggered,
            "typed_key": selected_key,
            "stable_gaze": stable_gaze,
        }

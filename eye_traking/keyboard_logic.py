import time
from collections import Counter  # NUEVO: Para contar las miradas

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
        
        # NUEVO: Historial de miradas para eliminar el ruido
        self.gaze_history = []
        self.history_size = 5  # Requiere 5 lecturas consistentes
        
        self.last_move_time = time.time()
        self.move_cooldown = 1.5  
        
        self.last_blink_time = time.time()
        self.blink_cooldown = 1.5 
        
    def _clamp_cursor(self):
        self.row = max(0, min(self.row, len(self.keys) - 1))
        self.col = max(0, min(self.col, len(self.keys[self.row]) - 1))

    def update_state(self, gaze_direction, is_blinking):
        current_time = time.time()
        moved = False
        click_triggered = False
        selected_key = None
        
        # NUEVO: Agregamos la mirada actual al historial
        self.gaze_history.append(gaze_direction)
        if len(self.gaze_history) > self.history_size:
            self.gaze_history.pop(0) # Borramos la lectura más vieja

        # NUEVO: Sacamos el "promedio" (la mirada que más se repite)
        stable_gaze = Counter(self.gaze_history).most_common(1)[0][0]
        
        # 1. Inteligencia de Movimiento (Ahora usa stable_gaze)
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
                # Al moverse, limpiamos el historial para evitar un doble salto
                self.gaze_history.clear() 
                self.last_move_time = current_time

        self._clamp_cursor()
        current_key = self.keys[self.row][self.col]

        # 2. Inteligencia de Selección (Clic)
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
            "stable_gaze": stable_gaze # Podemos mandar la mirada estabilizada también
        }
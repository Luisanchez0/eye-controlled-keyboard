import time

class KeyboardBrain:
    def __init__(self):
        # El mapa lógico del teclado (tu compañero puede cambiar cómo se ve, 
        # pero esta es la estructura que tú usas para moverte).
        self.keys = [
            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'Ñ'],
            ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '-'],
            ['SPACE', 'BACKSPACE', 'ENTER']
        ]
        
        # Cursor lógico (iniciamos en el centro, fila 1, columna 4)
        self.row = 1
        self.col = 4
        
        # Inteligencia de tiempos (Cooldowns) para que el cursor no vuele
        self.last_move_time = time.time()
        self.move_cooldown = 0.8  # Segundos para cambiar de tecla
        
        self.last_blink_time = time.time()
        self.blink_cooldown = 1.5 # Segundos para evitar doble clic
        
    def _clamp_cursor(self):
        """Asegura que el cursor nunca se salga de los límites del arreglo"""
        self.row = max(0, min(self.row, len(self.keys) - 1))
        self.col = max(0, min(self.col, len(self.keys[self.row]) - 1))

    def update_state(self, gaze_direction, is_blinking):
        """
        Esta es la única función que tu compañero necesita llamar.
        Entrada: "RIGHT", "LEFT", etc. y True/False del parpadeo.
        Salida: Un diccionario con el estado actual del sistema.
        """
        current_time = time.time()
        moved = False
        click_triggered = False
        selected_key = None
        
        # 1. Inteligencia de Movimiento
        if current_time - self.last_move_time > self.move_cooldown:
            if gaze_direction == "RIGHT":
                self.col += 1
                moved = True
            elif gaze_direction == "LEFT":
                self.col -= 1
                moved = True
            elif gaze_direction == "DOWN":
                self.row += 1
                moved = True
            elif gaze_direction == "UP":
                self.row -= 1
                moved = True
            
            if moved:
                self.last_move_time = current_time

        self._clamp_cursor()
        current_key = self.keys[self.row][self.col]

        # 2. Inteligencia de Selección (Clic)
        if is_blinking and (current_time - self.last_blink_time > self.blink_cooldown):
            click_triggered = True
            selected_key = current_key
            self.last_blink_time = current_time

        # 3. Empaquetar la información para el equipo de interfaz
        return {
            "cursor_row": self.row,
            "cursor_col": self.col,
            "current_key": current_key,
            "is_clicking": click_triggered,
            "typed_key": selected_key
        }
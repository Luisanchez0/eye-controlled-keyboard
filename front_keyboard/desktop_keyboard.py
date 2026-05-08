import tkinter as tk
from tkinter import ttk
import sys
import os
import json
from collections import deque
from statistics import median
from PIL import Image, ImageTk

class DesktopKeyboardApp:
    def __init__(self, brain_keys):
        self.root = tk.Tk()
        self.root.title("Eye-Controlled Keyboard")
        self.brain_keys = brain_keys

        # Calibration state
        self.cal_sequences = {
            "gaze": ['CENTER', 'LEFT', 'RIGHT', 'UP', 'DOWN'],
            "head": ['CENTER', 'LEFT', 'RIGHT'],
        }
        self.control_mode = "head"
        self.cal_sequence = list(self.cal_sequences[self.control_mode])
        self.cal_index = -1
        self.cal_points = {}
        self.calibrated = False
        self.cal_params = {}
        self.mode_calibration = {"gaze": None, "head": None}
        self.profile_path = os.path.join(os.path.expanduser("~"), ".eye_keyboard_profiles.json")
        self.latest_gaze_point = None
        self.latest_control_point = None
        self.gaze_samples = deque(maxlen=18)
        self._on_camera_change_cb = None
        self.key_boxes = []

        self._build_ui()

        # Track current highlighted position
        self.current_pos = (0, 0)

        # Camera preview image ref
        self._cam_photo = None
        self._load_profiles()
        self.set_control_mode(self.control_mode)

    def _build_ui(self):
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        ttk.Label(top_frame, text="Typed text:").pack(side=tk.LEFT)
        self.text_display = tk.Text(top_frame, width=60, height=3, wrap=tk.WORD)
        self.text_display.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        # Controls frame (calibration + camera preview)
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(side=tk.TOP, fill=tk.X, padx=8)

        self.cal_btn = ttk.Button(ctrl_frame, text="Iniciar calibracion", command=self.start_calibration)
        self.cal_btn.pack(side=tk.LEFT, padx=4)

        self.record_btn = ttk.Button(ctrl_frame, text="Registrar punto", command=self.record_point, state=tk.DISABLED)
        self.record_btn.pack(side=tk.LEFT, padx=4)

        ttk.Label(ctrl_frame, text="Camara:").pack(side=tk.LEFT, padx=(10, 2))
        self.camera_var = tk.StringVar(value="0")
        self.camera_selector = ttk.Combobox(ctrl_frame, textvariable=self.camera_var, width=6, state="readonly")
        self.camera_selector.pack(side=tk.LEFT, padx=2)
        self.camera_selector.bind("<<ComboboxSelected>>", self._on_camera_selected)

        self.cal_label = ttk.Label(ctrl_frame, text="Calibracion no iniciada")
        self.cal_label.pack(side=tk.LEFT, padx=8)

        self.cal_step_label = ttk.Label(ctrl_frame, text="Paso 0/5")
        self.cal_step_label.pack(side=tk.LEFT, padx=8)

        self.cal_help_label = ttk.Label(
            self.root,
            text="Pulsa 'Iniciar calibracion' y sigue el punto verde. Luego pulsa 'Registrar punto' en cada posicion.",
            wraplength=880,
            justify=tk.LEFT,
        )
        self.cal_help_label.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 0))

        self.cal_progress = ttk.Progressbar(
            self.root,
            maximum=len(self.cal_sequence),
            value=0,
            mode="determinate",
        )
        self.cal_progress.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(2, 6))

        tuning_frame = ttk.LabelFrame(self.root, text="Sensibilidad")
        tuning_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))

        self.deadzone_var = tk.DoubleVar(value=0.08)
        self.move_cooldown_var = tk.DoubleVar(value=0.45)
        self.blink_cooldown_var = tk.DoubleVar(value=0.75)

        ttk.Label(tuning_frame, text="Deadzone").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=4)
        deadzone_scale = ttk.Scale(
            tuning_frame,
            from_=0.04,
            to=0.30,
            variable=self.deadzone_var,
            command=self._on_tuning_changed,
        )
        deadzone_scale.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.deadzone_value_label = ttk.Label(tuning_frame, text=f"{self.deadzone_var.get():.2f}")
        self.deadzone_value_label.grid(row=0, column=2, sticky="e", padx=(4, 8), pady=4)

        ttk.Label(tuning_frame, text="Velocidad cursor").grid(row=1, column=0, sticky="w", padx=(8, 4), pady=4)
        move_scale = ttk.Scale(
            tuning_frame,
            from_=0.15,
            to=1.20,
            variable=self.move_cooldown_var,
            command=self._on_tuning_changed,
        )
        move_scale.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self.move_cooldown_value_label = ttk.Label(tuning_frame, text=f"{self.move_cooldown_var.get():.2f}s")
        self.move_cooldown_value_label.grid(row=1, column=2, sticky="e", padx=(4, 8), pady=4)

        ttk.Label(tuning_frame, text="Cooldown parpadeo").grid(row=2, column=0, sticky="w", padx=(8, 4), pady=4)
        blink_scale = ttk.Scale(
            tuning_frame,
            from_=0.20,
            to=1.50,
            variable=self.blink_cooldown_var,
            command=self._on_tuning_changed,
        )
        blink_scale.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        self.blink_cooldown_value_label = ttk.Label(tuning_frame, text=f"{self.blink_cooldown_var.get():.2f}s")
        self.blink_cooldown_value_label.grid(row=2, column=2, sticky="e", padx=(4, 8), pady=4)
        tuning_frame.columnconfigure(1, weight=1)

        self.gaze_debug_label = ttk.Label(self.root, text="Gaze: --")
        self.gaze_debug_label.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))
        self.camera_status_label = ttk.Label(self.root, text="Camara activa: --")
        self.camera_status_label.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))

        # Camera preview
        self.cam_label = ttk.Label(ctrl_frame)
        self.cam_label.pack(side=tk.RIGHT, padx=8)

        # Canvas for keyboard + cursor
        self.canvas = tk.Canvas(self.root, width=900, height=400, bg="#222")
        self.canvas.pack(padx=8, pady=8)

        self.key_items = []
        self._draw_keyboard()

        # Cursor dot id
        self.cursor_dot = None

        # Close handling
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_close_cb = None

    def _on_tuning_changed(self, _event=None):
        self.deadzone_value_label.config(text=f"{self.deadzone_var.get():.2f}")
        self.move_cooldown_value_label.config(text=f"{self.move_cooldown_var.get():.2f}s")
        self.blink_cooldown_value_label.config(text=f"{self.blink_cooldown_var.get():.2f}s")

    def _is_valid_calibration(self, params):
        if not isinstance(params, dict):
            return False
        required = {"x_min", "x_max", "y_min", "y_max", "x_span", "y_span"}
        if not required.issubset(params):
            return False
        return all(isinstance(params[k], (int, float)) for k in required)

    def _load_profiles(self):
        if not os.path.exists(self.profile_path):
            return
        try:
            with open(self.profile_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"WARN: no se pudo cargar perfil de calibracion: {exc}", file=sys.stderr)
            return

        if not isinstance(payload, dict):
            return
        for mode in self.cal_sequences:
            params = payload.get(mode)
            if self._is_valid_calibration(params):
                self.mode_calibration[mode] = params

    def _save_profiles(self):
        payload = {
            mode: params for mode, params in self.mode_calibration.items()
            if self._is_valid_calibration(params)
        }
        try:
            with open(self.profile_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=True, indent=2)
        except OSError as exc:
            print(f"WARN: no se pudo guardar perfil de calibracion: {exc}", file=sys.stderr)

    def set_control_mode(self, mode):
        if mode not in self.cal_sequences:
            return
        self.control_mode = mode
        self.cal_sequence = list(self.cal_sequences[mode])
        self.cal_progress.config(maximum=len(self.cal_sequence))
        saved = self.mode_calibration.get(mode)
        if self._is_valid_calibration(saved):
            self.cal_params = saved
            self.calibrated = True
            self.cal_label.config(text=f"Calibracion cargada ({mode})")
            self.cal_help_label.config(text="Perfil cargado. Puedes recalibrar si notas drift.")
        else:
            self.cal_params = {}
            self.calibrated = False
            self.cal_label.config(text=f"Calibracion no iniciada ({mode})")
            self.cal_help_label.config(text="Pulsa 'Iniciar calibracion' para mejorar precision.")
        self.cal_step_label.config(text=f"Paso 0/{len(self.cal_sequence)}")
        self.cal_progress.config(value=0)
        self._on_tuning_changed()

    def get_runtime_tuning(self):
        return {
            "deadzone": float(self.deadzone_var.get()),
            "move_cooldown": float(self.move_cooldown_var.get()),
            "blink_cooldown": float(self.blink_cooldown_var.get()),
        }

    def _draw_keyboard(self):
        self.canvas.delete("all")
        self.key_items = []
        self.key_boxes = []
        margin_x = 20
        margin_y = 20
        key_w = 70
        key_h = 70
        spacing = 8

        y = margin_y
        for row_idx, row in enumerate(self.brain_keys):
            x = margin_x
            row_items = []
            for col_idx, key in enumerate(row):
                rect = self.canvas.create_rectangle(x, y, x + key_w, y + key_h, fill="#444", outline="#999", width=2)
                text = self.canvas.create_text(x + key_w/2, y + key_h/2, text=key, fill="white", font=("Arial", 14, "bold"))
                row_items.append((rect, text))
                self.key_boxes.append(
                    {
                        "row": row_idx,
                        "col": col_idx,
                        "key": key,
                        "x0": x,
                        "y0": y,
                        "x1": x + key_w,
                        "y1": y + key_h,
                        "cx": x + key_w / 2,
                        "cy": y + key_h / 2,
                    }
                )
                x += key_w + spacing
            self.key_items.append(row_items)
            y += key_h + spacing

    def set_on_close(self, cb):
        self._on_close_cb = cb

    def set_on_camera_change(self, cb):
        self._on_camera_change_cb = cb

    def set_camera_options(self, camera_indices, selected_index=None):
        values = [str(idx) for idx in camera_indices] if camera_indices else ["0"]
        self.camera_selector["values"] = values
        if selected_index is None or str(selected_index) not in values:
            self.camera_var.set(values[0])
        else:
            self.camera_var.set(str(selected_index))

    def set_camera_status(self, message):
        self.camera_status_label.config(text=message)

    def _on_camera_selected(self, _event=None):
        if not self._on_camera_change_cb:
            return
        selected = self.camera_var.get().strip()
        if not selected:
            return
        try:
            camera_index = int(selected)
        except ValueError:
            return
        self._on_camera_change_cb(camera_index)

    def _on_close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.root.quit()

    def start_calibration(self):
        self.cal_sequence = list(self.cal_sequences[self.control_mode])
        self.cal_points = {}
        self.cal_index = 0
        self.calibrated = False
        self.gaze_samples.clear()
        self.cal_btn.config(text="Recalibrar")
        self.record_btn.config(state=tk.NORMAL)
        self.cal_progress.config(maximum=len(self.cal_sequence), value=0)
        self._update_calibration_ui()

    def record_point(self):
        if self.cal_index < 0 or self.cal_index >= len(self.cal_sequence):
            self.cal_label.config(text="Calibracion inactiva")
            self.cal_help_label.config(text="Pulsa 'Iniciar calibracion' para comenzar.")
            return

        if self.latest_control_point is None:
            self.cal_label.config(text="No se detecta control")
            self.cal_help_label.config(text="Ajusta tu posicion frente a la camara y vuelve a pulsar 'Registrar punto'.")
            return

        if len(self.gaze_samples) < 6:
            self.cal_label.config(text="Mantén posicion un momento")
            self.cal_help_label.config(text="Espera ~1 segundo con posicion estable y vuelve a registrar.")
            return

        avg_x = median(p[0] for p in self.gaze_samples)
        avg_y = median(p[1] for p in self.gaze_samples)
        point = self.cal_sequence[self.cal_index]
        self.cal_points[point] = (avg_x, avg_y)
        self.cal_index += 1
        self.gaze_samples.clear()

        if self.cal_index >= len(self.cal_sequence):
            self.cal_index = -1
            self._finalize_calibration()
        else:
            self._update_calibration_ui()

    def _finalize_calibration(self):
        # Compute calibration params based on collected points
        required_points = set(self.cal_sequence)
        if not required_points.issubset(self.cal_points.keys()):
            self.cal_label.config(text="Calibracion fallida")
            self.cal_help_label.config(text="No se registraron todos los puntos. Reinicia la calibracion.")
            self.record_btn.config(state=tk.DISABLED)
            self.calibrated = False
            return

        c = self.cal_points
        cx, cy = c['CENTER']
        lx, _ = c['LEFT']
        rx, _ = c['RIGHT']
        if 'UP' in c and 'DOWN' in c:
            _, uy = c['UP']
            _, dy = c['DOWN']
        else:
            uy = cy - 0.16
            dy = cy + 0.16

        x_min = min(lx, rx, cx)
        x_max = max(lx, rx, cx)
        y_min = min(uy, dy, cy)
        y_max = max(uy, dy, cy)
        x_span = max(x_max - x_min, 1e-6)
        y_span = max(y_max - y_min, 1e-6)

        self.cal_params = {
            'x_min': x_min,
            'x_max': x_max,
            'y_min': y_min,
            'y_max': y_max,
            'x_span': x_span,
            'y_span': y_span,
        }
        self.calibrated = True
        self.mode_calibration[self.control_mode] = dict(self.cal_params)
        self._save_profiles()
        self.record_btn.config(state=tk.DISABLED)
        self.cal_progress.config(value=len(self.cal_sequence))
        self.cal_label.config(text="Calibracion completada")
        self.cal_step_label.config(text=f"Paso {len(self.cal_sequence)}/{len(self.cal_sequence)}")
        self.cal_help_label.config(text=f"Listo. Perfil {self.control_mode} guardado. Si notas drift, pulsa 'Recalibrar'.")

    def _current_calibration_target(self):
        if self.cal_index < 0 or self.cal_index >= len(self.cal_sequence):
            return None
        return self.cal_sequence[self.cal_index]

    def _target_to_canvas(self, target):
        if target == 'CENTER':
            return 0.5, 0.5
        if target == 'LEFT':
            return 0.25, 0.5
        if target == 'RIGHT':
            return 0.75, 0.5
        if target == 'UP':
            return 0.5, 0.25
        if target == 'DOWN':
            return 0.5, 0.75
        return 0.5, 0.5

    def _key_from_point(self, point):
        if point is None or not self.key_boxes:
            return None

        px, py = point
        canvas_w = int(self.canvas.cget("width"))
        canvas_h = int(self.canvas.cget("height"))
        x = px * canvas_w
        y = py * canvas_h

        for box in self.key_boxes:
            if box["x0"] <= x <= box["x1"] and box["y0"] <= y <= box["y1"]:
                return box

        return min(
            self.key_boxes,
            key=lambda box: (box["cx"] - x) ** 2 + (box["cy"] - y) ** 2,
        )

    def _update_calibration_ui(self):
        target = self._current_calibration_target()
        if target is None:
            return
        step = self.cal_index + 1
        total = len(self.cal_sequence)
        self.cal_label.config(text=f"Calibrando: {target}")
        self.cal_step_label.config(text=f"Paso {step}/{total}")
        self.cal_progress.config(value=self.cal_index)
        action = "Mueve la cabeza hacia" if self.control_mode == "head" else "Mira al punto verde en"
        self.cal_help_label.config(
            text=f"{action} {target} y pulsa 'Registrar punto'."
        )

    def apply_calibration(self, gaze_point):
        # gaze_point is the iris position normalized inside the eye, not the
        # absolute pupil position in the camera frame.
        if not self.calibrated or gaze_point is None:
            return gaze_point
        px, py = gaze_point
        nx = (px - self.cal_params['x_min']) / self.cal_params['x_span']
        ny = (py - self.cal_params['y_min']) / self.cal_params['y_span']
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))
        return (nx, ny)

    def classify_gaze(self, gaze_point, allow_uncalibrated=False):
        if gaze_point is None:
            return None

        if self.calibrated:
            mapped = self.apply_calibration(gaze_point)
        elif allow_uncalibrated:
            mapped = gaze_point
        else:
            return None

        if not mapped:
            return None

        px, py = mapped
        deadzone = float(self.deadzone_var.get())
        dx = px - 0.5
        dy = py - 0.5

        if abs(dx) < deadzone and abs(dy) < deadzone:
            return "CENTER"
        if abs(dx) >= abs(dy):
            return "RIGHT" if dx > 0 else "LEFT"
        return "DOWN" if dy > 0 else "UP"

    def _get_text(self):
        return self.text_display.get("1.0", "end-1c")

    def _set_text(self, value):
        self.text_display.delete("1.0", tk.END)
        self.text_display.insert("1.0", value)
        self.text_display.see(tk.END)

    def _append_key(self, key):
        current = self._get_text()

        if key == "SPACE":
            self._set_text(current + " ")
        elif key == "BACKSPACE":
            self._set_text(current[:-1])
        elif key == "ENTER":
            self._set_text(current + "\n")
        else:
            self._set_text(current + str(key))

    def update_state(
        self,
        estado_teclado,
        pupils_normalized,
        gaze_point=None,
        control_point=None,
        frame_rgb=None,
        use_cursor_selection=False,
    ):
        current_point = control_point if control_point is not None else gaze_point
        self.latest_gaze_point = gaze_point
        self.latest_control_point = current_point
        if current_point is not None:
            self.gaze_samples.append(current_point)

        mapped_point = self.apply_calibration(current_point) if current_point is not None else None

        # Update camera preview
        if frame_rgb is not None:
            try:
                img = Image.fromarray(frame_rgb)
                img_tk = ImageTk.PhotoImage(image=img)
                self._cam_photo = img_tk
                self.cam_label.config(image=img_tk)
            except (ValueError, RuntimeError, tk.TclError) as exc:
                print(f"WARN preview update failed: {exc}", file=sys.stderr)

        row = estado_teclado.get("cursor_row", 0)
        col = estado_teclado.get("cursor_col", 0)

        # Update typed text if a click occurred
        focused_box = None if use_cursor_selection else self._key_from_point(mapped_point)
        focused_key = focused_box["key"] if focused_box is not None else None

        if estado_teclado.get("is_clicking"):
            if use_cursor_selection:
                key_to_type = estado_teclado.get("typed_key")
            else:
                key_to_type = focused_key if focused_key is not None else estado_teclado.get("typed_key")
            if key_to_type is not None:
                self._append_key(key_to_type)

        # Highlight current key
        if focused_box is not None:
            self._highlight_key(focused_box["row"], focused_box["col"])
        else:
            self._highlight_key(row, col)

        # If calibrating, draw a visual target on canvas for the current point
        target = self._current_calibration_target()
        if target is not None:
            nx, ny = self._target_to_canvas(target)
            cw = int(self.canvas.cget('width'))
            ch = int(self.canvas.cget('height'))
            tx = int(nx * cw)
            ty = int(ny * ch)
            self._draw_target(tx, ty)
        else:
            self._clear_target()

        # Draw cursor based on gaze direction, not absolute camera position.
        if mapped_point is not None:
            px, py = mapped_point
            self.gaze_debug_label.config(text=f"Control: x={px:.2f}, y={py:.2f}")
            px = max(0.0, min(1.0, px))
            py = max(0.0, min(1.0, py))
            canvas_w = int(self.canvas.cget("width"))
            canvas_h = int(self.canvas.cget("height"))
            cx = int(px * canvas_w)
            cy = int(py * canvas_h)
            self._draw_cursor(cx, cy)
        else:
            self.gaze_debug_label.config(text="Control: --")
            self._hide_cursor()

    def _draw_target(self, x, y, r=16):
        # draw or move a small target circle
        if not hasattr(self, '_target_id') or self._target_id is None:
            self._target_id = self.canvas.create_oval(x - r, y - r, x + r, y + r, outline='#0f0', width=3)
        else:
            try:
                self.canvas.coords(self._target_id, x - r, y - r, x + r, y + r)
            except tk.TclError as exc:
                print(f"WARN target update failed: {exc}", file=sys.stderr)

    def _clear_target(self):
        if hasattr(self, '_target_id') and self._target_id is not None:
            try:
                self.canvas.delete(self._target_id)
            except tk.TclError as exc:
                print(f"WARN target clear failed: {exc}", file=sys.stderr)
            self._target_id = None

    def show_error(self, message):
        self.cal_label.config(text=f"Error: {message}")
        self.cal_help_label.config(text="Corrige el error y vuelve a iniciar la calibracion.")

    def _highlight_key(self, row, col):
        # Reset previous
        for r_idx, row_items in enumerate(self.key_items):
            for c_idx, (rect, text) in enumerate(row_items):
                color = "#666" if (r_idx, c_idx) != (row, col) else "#1e90ff"
                self.canvas.itemconfigure(rect, fill=color)

    def _draw_cursor(self, x, y):
        r = 8
        if self.cursor_dot is None:
            self.cursor_dot = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill="#ff0")
        else:
            self.canvas.coords(self.cursor_dot, x - r, y - r, x + r, y + r)

    def _hide_cursor(self):
        if self.cursor_dot is not None:
            self.canvas.delete(self.cursor_dot)
            self.cursor_dot = None

    def mainloop(self, poll_callback=None, poll_interval=50):
        # poll_callback will be called periodically via after
        if poll_callback:
            def _poll():
                try:
                    poll_callback()
                finally:
                    self.root.after(poll_interval, _poll)
            self.root.after(poll_interval, _poll)

        self.root.mainloop()

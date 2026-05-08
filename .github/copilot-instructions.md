# Copilot instructions for `eye-controlled-keyboard`

## Commands used in this repository

```bash
# Install runtime dependencies
python3 -m pip install -r requirements.txt

# Run the desktop eye-tracking keyboard demo
python3 eye_traking/run_eye_tracker_test.py

# Run against a specific camera
python3 eye_traking/run_eye_tracker_test.py --camera 1
```

There is currently no committed automated test suite or lint configuration. `requirements.txt` only includes commented optional dev tools (`pytest`, `black`, `flake8`, `pylint`), so do not assume CI-style test/lint commands exist.

## High-level architecture

The app is a real-time local desktop pipeline split across three modules:

1. `eye_traking/eye_traker.py` (`EyeDetector`): reads MediaPipe face landmarks from camera frames, computes normalized gaze point (`x_ratio`, `y_ratio`), classifies coarse direction (`LEFT/RIGHT/UP/DOWN/CENTER`), and detects blink via eye aspect ratio.
2. `eye_traking/keyboard_logic.py` (`KeyboardBrain`): converts gaze+blink events into keyboard navigation/selection state. It smooths gaze with a short history window and applies cooldowns for both movement and blink-triggered selection.
3. `front_keyboard/desktop_keyboard.py` (`DesktopKeyboardApp`): Tkinter UI showing keyboard grid, typed text, camera preview, calibration flow, and cursor visualization. Calibration remaps gaze points per user and can override detector direction.

`eye_traking/run_eye_tracker_test.py` wires everything together:
- camera capture and detector inference run in a background thread,
- GUI runs on the main thread,
- thread communication uses a `Queue(maxsize=1)` with overwrite-on-full behavior (`put_latest`) to keep only the latest frame packet.

## Codebase-specific conventions

- Keep gaze direction labels exactly as uppercase tokens: `LEFT`, `RIGHT`, `UP`, `DOWN`, `CENTER` across detector, calibration, and keyboard logic.
- Preserve the “latest packet wins” queue pattern in the runtime loop to avoid UI lag from stale frames.
- Keep calibration behavior as a precedence layer: `DesktopKeyboardApp.classify_gaze(gaze_point)` result is used first, then it falls back to detector direction.
- Keyboard input semantics are centralized in `DesktopKeyboardApp._append_key` (`SPACE`, `BACKSPACE`, `ENTER` special handling). Do not duplicate key-text mutation logic elsewhere.
- Import paths currently rely on the existing package/file names (`eye_traking`, `eye_traker.py`); keep those names consistent unless doing a full coordinated rename.

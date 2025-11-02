# Counter-Strike 2 Counter-Strafe Training Tool

A real-time training overlay that helps players practice counter-strafing — the timing technique used in games like _Counter-Strike 2_ to stop movement before firing for maximum accuracy.

The tool monitors your keyboard and mouse inputs, visualizes your timing, and provides both visual and audio feedback on how consistent your counter-strafes are.

---

## Overview

Counter-strafing involves pressing the opposite movement key briefly to stop momentum before shooting. For example, when moving left (`A`), you release `A`, tap `D` to cancel your momentum, wait roughly 60–110ms, and then shoot.

This tool measures that interval — from the moment you press the counter-strafe key to when you fire — and classifies it by accuracy.

## Preview

![Overlay Preview](docs/preview.png)

---

## Disclaimer

This tool works by listening for global keyboard and mouse inputs to measure timing accuracy.
Because of that, it’s strongly recommended that you only use it in offline servers, workshop maps, or non-competitive modes.

Running any external program that hooks or monitors input while connected to competitive or anti-cheat-protected servers (such as VAC-secured matchmaking) may carry a risk of false positives or account restrictions.

Use responsibly and at your own discretion.

---

## Features

- Real-time tracking of `A` and `D` key inputs
- Visual timing bar showing when your shot occurred relative to ideal timing windows
- Sound feedback for different timing categories (`early`, `perfect`, `ok`, `bad`, `hold`)
- Transparent, always-on-top overlay that can be dragged anywhere on screen
- Basic statistics display with recent performance data

---

## Timing Categories

| Category | Range (ms) | Description                                   |
| -------- | ---------- | --------------------------------------------- |
| Early    | < 60       | Too quick — you may not be fully stopped      |
| Perfect  | 60–110     | Ideal counter-strafe timing                   |
| Okay     | 110–200    | Acceptable, but slightly slow                 |
| Poor     | > 200      | Too slow, shot fired while still decelerating |

---

## Installation

1. **Clone or download** this repository.
2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Add your sound files under `audio/`:

   ```
   audio/
   ├── early.mp3
   ├── perfect.mp3
   ├── ok.mp3
   ├── bad.mp3
   └── hold.mp3
   ```

4. Run the script:

   ```bash
   python counter_strafe_trainer.py
   ```

---

## Usage

1. Start the program. A small overlay window will appear in the top-right corner. Drag the border to reposition.
2. In-game, follow the standard counter-strafe pattern:

   ```
   Hold A → Release A → Tap D → Wait 60ms+ → Shoot
   ```

3. The overlay updates in real time:

   - The timing bar shows your shot relative to the ideal window.
   - The border color and label give immediate feedback.
   - Stats update after each attempt.

4. Press **ESC** to pause or resume tracking.
5. Click **Reset Stats** in the overlay to clear your session data.
6. Click **Quit** to exit the application.

---

## Configuration

You can adjust the sensitivity of what counts as “holding too long” before moving the opposite direction by editing:

```python
self.max_hold_time_ms = 60
```

inside the `CounterStrafeTrainer` class.

---

## Platform Notes

- Works on Windows; limited transparency behavior on macOS and Linux.
- Uses `pynput` for global keyboard/mouse listening and `pygame` for sound playback.
- The overlay uses `tkinter` and stays above fullscreen games through Windows API adjustments.

---

## License

MIT License — feel free to modify and share.

The voice feedback clips used in this project were generated with ElevenLabs (voice ID: YOq2y2Up4RgXP2HyXjE5).

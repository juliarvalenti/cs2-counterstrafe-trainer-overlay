"""
Counter-Strike Counter-Strafe Training Tool
Monitors your counter-strafing technique and provides real-time feedback
"""

import tkinter as tk
from pynput import keyboard, mouse
import time
from collections import deque
import threading
import pygame
import os


class CounterStrafeTrainer:
    def __init__(self):
        # Movement state tracking
        self.keys_held = set()  # Track all currently held movement keys
        self.last_movement_direction = None  # 'a' or 'd'
        self.counter_strafe_press_time = None  # When counter-strafe key was pressed
        self.counter_strafe_release_time = None  # When counter-strafe key was released
        self.awaiting_shot = False  # Waiting for shot after counter-strafe
        self.active_tracking = False  # Whether we're actively tracking a counter-strafe
        self.tracking_update_job = None  # Store the after() job ID

        # Statistics
        self.strafe_timings = deque(maxlen=20)  # Keep last 20 counter-strafes
        self.session_stats = {
            "total_attempts": 0,
            "perfect": 0,  # 80-110ms hold
            "good": 0,  # 110-150ms hold
            "okay": 0,  # 150-200ms hold
            "poor": 0,  # >200ms or <80ms hold
        }

        # UI
        self.root = None
        self.feedback_label = None
        self.stats_label = None
        self.timing_label = None
        self.timing_canvas = None
        self.running = False

        # Key mappings (A and D only for now)
        self.movement_keys = {"a", "d"}
        self.opposite_key = {"a": "d", "d": "a"}

        # Configurable settings
        self.max_hold_time_ms = (
            60  # Maximum time to hold counter-strafe before moving opposite direction
        )

        # Initialize audio
        self.sounds = {}
        self.init_audio()

    def init_audio(self):
        """Initialize pygame mixer and load sound files"""
        try:
            pygame.mixer.init()

            # Get the directory where the script is located
            script_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "audio"
            )

            # Load sound files
            sound_files = {
                "early": "early.mp3",
                "perfect": "perfect.mp3",
                "ok": "ok.mp3",
                "bad": "bad.mp3",
                "hold": "hold.mp3",
            }

            for key, filename in sound_files.items():
                filepath = os.path.join(script_dir, filename)
                if os.path.exists(filepath):
                    try:
                        self.sounds[key] = pygame.mixer.Sound(filepath)
                    except Exception as e:
                        print(f"Warning: Could not load {filename}: {e}")
                else:
                    print(f"Warning: Sound file not found: {filepath}")

        except Exception as e:
            print(f"Warning: Could not initialize audio: {e}")

    def play_sound(self, sound_key):
        """Play a sound effect"""
        try:
            if sound_key in self.sounds:
                # Stop any currently playing sound
                pygame.mixer.stop()
                # Play the new sound
                self.sounds[sound_key].play()
        except Exception as e:
            # Silently fail if audio doesn't work
            pass

    def create_overlay(self):
        """Create a transparent overlay window"""
        self.root = tk.Tk()
        self.root.title("Counter-Strafe Trainer")

        # Window configuration
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.overrideredirect(True)

        # Platform-specific: Force window above fullscreen apps
        import platform

        if platform.system() == "Windows":
            # Windows-specific code to stay above fullscreen
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            # HWND_TOPMOST = -1, SWP_NOMOVE | SWP_NOSIZE = 0x0003
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0003)
            # Set as a tool window to stay above fullscreen
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TOPMOST = 0x00000008
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            )

        # Position in top-right corner
        window_width = 380
        window_height = 340
        screen_width = self.root.winfo_screenwidth()
        x_position = screen_width - window_width - 20
        y_position = 20

        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        self.root.configure(bg="#1a1a1a")

        # Create a border frame that we can change colors
        self.border_frame = tk.Frame(self.root, bg="#333333", bd=0)
        self.border_frame.place(x=0, y=0, width=window_width, height=window_height)

        # Inner frame for content
        self.content_frame = tk.Frame(self.border_frame, bg="#1a1a1a", bd=0)
        self.content_frame.place(
            x=12, y=12, width=window_width - 24, height=window_height - 24
        )

        # Make draggable (bind to border frame)
        self.border_frame.bind("<Button-1>", self.start_move)
        self.border_frame.bind("<B1-Motion>", self.do_move)

        # Title
        title = tk.Label(
            self.content_frame,
            text="Counter-Strafe Trainer",
            font=("Arial", 14, "bold"),
            bg="#1a1a1a",
            fg="#00ff00",
        )
        title.pack(pady=5)

        # Current timing feedback
        self.timing_label = tk.Label(
            self.content_frame,
            text="Last Strafe: --",
            font=("Arial", 12),
            bg="#1a1a1a",
            fg="#ffffff",
        )
        self.timing_label.pack(pady=5)

        # Visual timing bar
        self.timing_canvas = tk.Canvas(
            self.content_frame, width=340, height=60, bg="#1a1a1a", highlightthickness=0
        )
        self.timing_canvas.pack(pady=5)
        self.draw_timing_bar()

        # Feedback label
        self.feedback_label = tk.Label(
            self.content_frame,
            text="Waiting for input...\nPattern: Hold A → Release A → Tap D → Wait 80ms+ → Shoot",
            font=("Arial", 10),
            bg="#1a1a1a",
            fg="#888888",
            wraplength=350,
            justify="center",
        )
        self.feedback_label.pack(pady=5)

        # Statistics
        self.stats_label = tk.Label(
            self.content_frame,
            text=self.get_stats_text(),
            font=("Arial", 9),
            bg="#1a1a1a",
            fg="#cccccc",
            justify="left",
        )
        self.stats_label.pack(pady=5)

        # Control buttons
        button_frame = tk.Frame(self.content_frame, bg="#1a1a1a")
        button_frame.pack(pady=5)

        reset_btn = tk.Button(
            button_frame,
            text="Reset Stats",
            command=self.reset_stats,
            bg="#333333",
            fg="#ffffff",
            relief="flat",
        )
        reset_btn.pack(side="left", padx=5)

        quit_btn = tk.Button(
            button_frame,
            text="Quit",
            command=self.quit_app,
            bg="#ff3333",
            fg="#ffffff",
            relief="flat",
        )
        quit_btn.pack(side="left", padx=5)

        # Instructions
        instructions = tk.Label(
            self.content_frame,
            text="ESC: pause/resume | Drag to move",
            font=("Arial", 8),
            bg="#1a1a1a",
            fg="#666666",
        )
        instructions.pack(pady=2)

        self.running = True

        # Periodic check to ensure window stays on top
        self.keep_on_top()

    def keep_on_top(self):
        """Periodically ensure window stays on top"""
        if self.root:
            self.root.attributes("-topmost", True)
            self.root.lift()
            self.root.after(1000, self.keep_on_top)  # Check every second

    def update_tracking_line(self):
        """Update the real-time tracking line while counter-strafing"""
        if not self.active_tracking or not self.counter_strafe_press_time:
            return

        # Calculate current hold time
        current_time = time.time()
        current_hold_ms = (current_time - self.counter_strafe_press_time) * 1000

        # Update the timing bar with current position
        self.draw_timing_bar(current_hold_ms, is_tracking=True)

        # Schedule next update (every 10ms for smooth animation)
        if self.active_tracking:
            self.tracking_update_job = self.root.after(10, self.update_tracking_line)

    def draw_timing_bar(self, shot_timing=None, release_timing=None, is_tracking=False):
        """Draw the timing bar visualization"""
        if not self.timing_canvas:
            return

        # Clear canvas
        self.timing_canvas.delete("all")

        # Constants
        bar_width = 320
        bar_height = 20
        bar_x = 10
        bar_y = 30

        # Define timing zones (in ms)
        # 0-60ms: Early (yellow-green)
        # 60-110ms: Perfect (green)
        # 110-150ms: Ok (orange)
        # 150-200ms: Ok (orange)
        # 200+ms: Bad (red)

        max_display_time = 250  # Display up to 250ms

        # Calculate zone widths
        def ms_to_x(ms):
            return bar_x + (ms / max_display_time) * bar_width

        # Draw background zones
        # Early zone (0-60ms) - Yellow-Green
        self.timing_canvas.create_rectangle(
            ms_to_x(0),
            bar_y,
            ms_to_x(60),
            bar_y + bar_height,
            fill="#aaff00",
            outline="",
        )

        # Perfect zone (60-110ms) - Green
        self.timing_canvas.create_rectangle(
            ms_to_x(60),
            bar_y,
            ms_to_x(110),
            bar_y + bar_height,
            fill="#00ff00",
            outline="",
        )

        # Ok zone (110-200ms) - Orange
        self.timing_canvas.create_rectangle(
            ms_to_x(110),
            bar_y,
            ms_to_x(200),
            bar_y + bar_height,
            fill="#ffaa00",
            outline="",
        )

        # Bad zone (200-250ms) - Red
        self.timing_canvas.create_rectangle(
            ms_to_x(200),
            bar_y,
            ms_to_x(250),
            bar_y + bar_height,
            fill="#ff4444",
            outline="",
        )

        # Draw labels
        self.timing_canvas.create_text(
            bar_x + bar_width / 2,
            bar_y - 10,
            text="Time from Counter-Strafe to Shot",
            fill="#cccccc",
            font=("Arial", 9, "bold"),
        )

        # Draw timing markers
        for ms in [60, 110, 200]:
            x = ms_to_x(ms)
            self.timing_canvas.create_line(
                x, bar_y, x, bar_y + bar_height, fill="#000000", width=2
            )
            self.timing_canvas.create_text(
                x,
                bar_y + bar_height + 10,
                text=f"{ms}",
                fill="#888888",
                font=("Arial", 8),
            )

        # Draw 0ms and 250ms labels
        self.timing_canvas.create_text(
            bar_x, bar_y + bar_height + 10, text="0", fill="#888888", font=("Arial", 8)
        )
        self.timing_canvas.create_text(
            bar_x + bar_width,
            bar_y + bar_height + 10,
            text="250ms",
            fill="#888888",
            font=("Arial", 8),
        )

        # Draw shot indicator if provided
        if shot_timing is not None:
            # Clamp to display range
            display_timing = min(shot_timing, max_display_time)
            shot_x = ms_to_x(display_timing)

            # Choose color based on whether we're tracking or showing final result
            if is_tracking:
                # Light blue for active tracking
                line_color = "#00ddff"
                line_width = 2
            else:
                # White for final shot
                line_color = "#ffffff"
                line_width = 3

            # Draw indicator line
            self.timing_canvas.create_line(
                shot_x,
                bar_y - 5,
                shot_x,
                bar_y + bar_height + 5,
                fill=line_color,
                width=line_width,
            )

            # Draw triangle pointer (only for final shot, not tracking)
            if not is_tracking:
                self.timing_canvas.create_polygon(
                    shot_x,
                    bar_y - 5,
                    shot_x - 5,
                    bar_y - 12,
                    shot_x + 5,
                    bar_y - 12,
                    fill="#ffffff",
                    outline="#ffffff",
                )

        # Draw release marker if provided (when counter-strafe key was released)
        if release_timing is not None and not is_tracking:
            display_release = min(release_timing, max_display_time)
            release_x = ms_to_x(display_release)

            # Draw dashed line for release point
            dash_length = 5
            for y in range(int(bar_y), int(bar_y + bar_height), dash_length * 2):
                self.timing_canvas.create_line(
                    release_x,
                    y,
                    release_x,
                    min(y + dash_length, bar_y + bar_height),
                    fill="#ffff00",
                    width=2,
                )

            # Draw diamond marker at top
            diamond_size = 4
            self.timing_canvas.create_polygon(
                release_x,
                bar_y - 8,
                release_x - diamond_size,
                bar_y - 4,
                release_x,
                bar_y,
                release_x + diamond_size,
                bar_y - 4,
                fill="#ffff00",
                outline="#ffff00",
            )

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def on_key_press(self, key):
        """Handle key press events"""
        if not self.running:
            return

        try:
            key_char = key.char.lower()
        except AttributeError:
            if key == keyboard.Key.esc:
                self.running = not self.running
                status = "RESUMED" if self.running else "PAUSED"
                self.update_feedback(f"Training {status}", "#ffaa00")
            return

        # Check if it's a movement key
        if key_char in self.movement_keys:
            current_time = time.time()

            # Add to held keys
            self.keys_held.add(key_char)

            # Check if this is a counter-strafe (pressing opposite direction)
            if self.last_movement_direction:
                expected_opposite = self.opposite_key.get(self.last_movement_direction)

                if key_char == expected_opposite:
                    # This is a counter-strafe!
                    self.counter_strafe_press_time = current_time
                    self.awaiting_shot = True
                    self.active_tracking = True

                    # Reset border to neutral for new attempt
                    if hasattr(self, "border_frame"):
                        self.border_frame.config(bg="#555555")

                    self.update_feedback(
                        f"Counter-strafing with {key_char.upper()}... hold it!",
                        "#00aaff",
                    )
                    # Start updating the tracking line
                    self.update_tracking_line()

            # Track which direction we're moving
            if key_char == "a":
                self.last_movement_direction = "a"
            elif key_char == "d":
                self.last_movement_direction = "d"

    def on_key_release(self, key):
        """Handle key release events"""
        if not self.running:
            return

        try:
            key_char = key.char.lower()
        except AttributeError:
            return

        # Remove from held keys
        if key_char in self.keys_held:
            self.keys_held.discard(key_char)

        # Track when counter-strafe key is released
        if (
            key_char in self.movement_keys
            and self.counter_strafe_press_time
            and self.awaiting_shot
        ):
            current_time = time.time()
            self.counter_strafe_release_time = current_time

    def on_click(self, x, y, button, pressed):
        """Handle mouse click events (shooting)"""
        if not self.running:
            return

        if pressed and button == mouse.Button.left:
            current_time = time.time()

            # Check if we're in a counter-strafe sequence
            if self.awaiting_shot and self.counter_strafe_press_time:

                # Calculate time from pressing counter-strafe key to shooting
                time_from_counterstrafe_ms = (
                    current_time - self.counter_strafe_press_time
                ) * 1000

                # Calculate time from releasing counter-strafe to shooting (if released)
                time_from_release_ms = None
                if self.counter_strafe_release_time:
                    time_from_release_ms = (
                        current_time - self.counter_strafe_release_time
                    ) * 1000

                # Evaluate the counter-strafe timing
                self.evaluate_strafe(time_from_counterstrafe_ms, time_from_release_ms)

                # Reset for next sequence
                self.reset_sequence()

    def reset_sequence(self):
        """Reset the counter-strafe sequence"""
        self.counter_strafe_press_time = None
        self.counter_strafe_release_time = None
        self.awaiting_shot = False
        self.active_tracking = False

        # Cancel any pending tracking updates
        if self.tracking_update_job:
            self.root.after_cancel(self.tracking_update_job)
            self.tracking_update_job = None

    def evaluate_strafe(self, time_from_counterstrafe_ms, time_from_release_ms=None):
        """Evaluate the counter-strafe timing and update UI"""
        self.session_stats["total_attempts"] += 1

        # Check if they held the counter-strafe key too long
        held_too_long = time_from_counterstrafe_ms > self.max_hold_time_ms

        if time_from_counterstrafe_ms < 60:
            # Early - still pretty good
            color = "#aaff00"
            feedback = f"Early! {time_from_counterstrafe_ms:.0f}ms"
            self.session_stats["good"] += 1
            self.strafe_timings.append(time_from_counterstrafe_ms)
            sound = "early"
        elif 60 <= time_from_counterstrafe_ms <= 110:
            # Perfect zone
            color = "#00ff00"
            feedback = f"🎯 PERFECT! {time_from_counterstrafe_ms:.0f}ms"
            self.session_stats["perfect"] += 1
            self.strafe_timings.append(time_from_counterstrafe_ms)
            sound = "perfect"
        elif 110 < time_from_counterstrafe_ms <= 150:
            # Ok timing
            color = "#ffaa00"
            feedback = f"Ok. {time_from_counterstrafe_ms:.0f}ms"
            self.session_stats["okay"] += 1
            self.strafe_timings.append(time_from_counterstrafe_ms)
            sound = "ok"
        elif 150 < time_from_counterstrafe_ms <= 200:
            # Still ok but slower
            color = "#ffaa00"
            feedback = f"Ok. {time_from_counterstrafe_ms:.0f}ms"
            self.session_stats["okay"] += 1
            self.strafe_timings.append(time_from_counterstrafe_ms)
            sound = "ok"
        else:
            # Too slow
            color = "#ff4444"
            feedback = f"Too slow. {time_from_counterstrafe_ms:.0f}ms"
            self.session_stats["poor"] += 1
            sound = "bad"

        # Check if they held the counter-strafe key too long
        if held_too_long:
            color = "#ff8800"
            feedback = f"⚠️ Held too long ({time_from_counterstrafe_ms:.0f}ms) - you started moving!"
            sound = "hold"

        # Play sound feedback
        self.play_sound(sound)

        # Update UI
        self.update_timing(time_from_counterstrafe_ms, color)
        self.update_feedback(feedback, color)
        self.update_stats()
        self.draw_timing_bar(
            time_from_counterstrafe_ms, time_from_release_ms, is_tracking=False
        )

    def update_timing(self, timing_ms, color):
        """Update the timing display"""
        if self.timing_label:
            self.timing_label.config(
                text=f"Last Shot: {timing_ms:.0f}ms after counterstrafe", fg=color
            )

    def update_feedback(self, message, color):
        """Update the feedback message"""
        if self.feedback_label:
            self.feedback_label.config(text=message, fg=color)

        # Flash the border with the result color
        self.flash_border(color)

    def flash_border(self, color):
        """Set the window border to the given color (persists until next shot)"""
        if hasattr(self, "border_frame"):
            # Set border to result color and keep it
            self.border_frame.config(bg=color)

    def get_stats_text(self):
        """Generate statistics text"""
        total = self.session_stats["total_attempts"]
        if total == 0:
            return "No strafes recorded yet"

        perfect_pct = (self.session_stats["perfect"] / total) * 100
        good_pct = (self.session_stats["good"] / total) * 100

        avg_timing = (
            sum(self.strafe_timings) / len(self.strafe_timings)
            if self.strafe_timings
            else 0
        )

        stats = f"""Session Stats:
Total Attempts: {total}
Perfect (60-110ms): {self.session_stats['perfect']} ({perfect_pct:.1f}%)
Early/Ok: {self.session_stats['good'] + self.session_stats['okay']}
Avg Time to Shot: {avg_timing:.0f}ms"""

        return stats

    def update_stats(self):
        """Update the statistics display"""
        if self.stats_label:
            self.stats_label.config(text=self.get_stats_text())

    def reset_stats(self):
        """Reset all statistics"""
        self.strafe_timings.clear()
        self.session_stats = {
            "total_attempts": 0,
            "perfect": 0,
            "good": 0,
            "okay": 0,
            "poor": 0,
        }
        self.reset_sequence()
        self.update_stats()
        self.update_feedback("Stats reset! Ready to train.", "#00ff00")

    def quit_app(self):
        """Quit the application"""
        self.running = False
        if self.root:
            self.root.quit()

    def start_listeners(self):
        """Start keyboard and mouse listeners in separate thread"""

        def listen():
            with keyboard.Listener(
                on_press=self.on_key_press, on_release=self.on_key_release
            ) as k_listener, mouse.Listener(on_click=self.on_click) as m_listener:
                k_listener.join()
                m_listener.join()

        listener_thread = threading.Thread(target=listen, daemon=True)
        listener_thread.start()

    def run(self):
        """Run the trainer"""
        self.create_overlay()
        self.start_listeners()
        self.root.mainloop()


if __name__ == "__main__":
    print("Starting Counter-Strafe Trainer...")
    print("\nCorrect Pattern:")
    print("1. Hold A (move left)")
    print("2. Release A")
    print("3. Tap D (counter-strafe - can be quick tap)")
    print("4. Wait 60ms+ after pressing D")
    print("5. Shoot (you're now stopped and accurate)")
    print("\nKey Point: The 60ms+ is measured from when you PRESS")
    print("the counter-strafe key to when you shoot, not how long you hold it!")
    print("\nNote: Don't hold the counter-strafe key too long (>60ms by default)")
    print("or you'll start moving in the opposite direction!")
    print("\nTo change max hold time, edit: trainer.max_hold_time_ms = 60")
    print("\nControls:")
    print("- ESC: pause/resume")
    print("- Drag window to reposition")
    print("- Goal: 60-110ms from counter-strafe to shot")
    print("\nStarting in 3 seconds...")
    time.sleep(3)

    trainer = CounterStrafeTrainer()
    trainer.run()

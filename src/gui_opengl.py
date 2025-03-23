import pygame
import sys
import numpy as np
import cv2
import threading
import time
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

WIDTH, HEIGHT = 1280, 720
UDP_PORT = 6666
FRAMERATE = 30


class GStreamerVideoOverlay:
    def __init__(self):
        self.frame_surface = None
        self.frame_lock = threading.Lock()
        self.running = True

        self.last_fps_time = time.time()
        self.fps = 0
        self.fps_alpha = 0.9  # Smoothing factor (higher = smoother)

        self.init_pygame()
        self.init_gstreamer()
        self.start_decoder_thread()

        # Control input
        self.throttle = 0.0
        self.steering = 0.0
        self.throttle_speed = 0.02
        self.steering_speed = 0.05
        self.friction = 0.02

    def init_gstreamer(self):
        pipeline_str = (
            f"udpsrc port={UDP_PORT} ! "
            "application/x-rtp, payload=96 ! "
            "rtph264depay ! h264parse ! avdec_h264 ! "
            "videoconvert ! video/x-raw,format=BGR ! appsink name=sink max-buffers=1 drop=true"
        )
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.appsink = self.pipeline.get_by_name("sink")
        self.appsink.set_property("emit-signals", True)
        self.appsink.set_property("sync", False)

    def init_pygame(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("GStreamer + Pygame Overlay")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 20)

    def start_decoder_thread(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        self.decode_thread = threading.Thread(target=self.decode_frames, daemon=True)
        self.decode_thread.start()

    def decode_frames(self):
        while self.running:
            sample = self.appsink.emit("try-pull-sample", Gst.SECOND // FRAMERATE)
            if sample:
                buf = sample.get_buffer()
                caps = sample.get_caps()
                width = caps.get_structure(0).get_value('width')
                height = caps.get_structure(0).get_value('height')

                success, map_info = buf.map(Gst.MapFlags.READ)
                if not success:
                    continue

                # Convert to NumPy image (BGR)
                frame_data = np.frombuffer(map_info.data, np.uint8)
                frame = frame_data.reshape((height, width, 3))
                buf.unmap(map_info)

                # Convert to RGB and create Pygame surface
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                surface = pygame.image.frombuffer(frame.tobytes(), (width, height), "RGB")
                surface = pygame.transform.scale(surface, (WIDTH, HEIGHT))

                with self.frame_lock:
                    self.frame_surface = surface
            else:
                time.sleep(0.001)

    def clamp(self, val, min_val, max_val):
        return max(min(val, max_val), min_val)

    def draw_overlay(self):
        # Steering indicator
        center_x = WIDTH // 2 + int(self.steering * 200)
        pygame.draw.rect(self.screen, (0, 255, 0), (center_x - 10, HEIGHT - 30, 20, 10))

        # Throttle bar
        bar_height = int(self.throttle * 200)
        pygame.draw.rect(self.screen, (0, 0, 255), (20, HEIGHT - bar_height - 20, 20, bar_height))

        # FPS display
        fps_text = self.font.render(f"FPS: {self.fps:.1f}", True, (255, 255, 255))
        self.screen.blit(fps_text, (WIDTH - 120, 20))

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False

            keys = pygame.key.get_pressed()

            # Throttle logic
            if keys[pygame.K_w]:
                self.throttle += self.throttle_speed
            elif keys[pygame.K_s]:
                self.throttle -= self.throttle_speed
            else:
                if abs(self.throttle) < 0.01:
                    self.throttle = 0.0
                elif self.throttle > 0:
                    self.throttle -= self.throttle_speed / 2
                elif self.throttle < 0:
                    self.throttle += self.throttle_speed / 2

            self.throttle = self.clamp(self.throttle, 0.0, 1.0)

            # Steering logic
            if keys[pygame.K_a]:
                self.steering -= self.steering_speed
            elif keys[pygame.K_d]:
                self.steering += self.steering_speed
            else:
                if abs(self.steering) < 0.01:
                    self.steering = 0.0
                elif self.steering > 0:
                    self.steering -= self.friction
                elif self.steering < 0:
                    self.steering += self.friction

            self.steering = self.clamp(self.steering, -1.0, 1.0)

            # Run GStreamer loop
            GLib.MainContext.default().iteration(False)

            # Draw video frame
            with self.frame_lock:
                if self.frame_surface:
                    self.screen.blit(self.frame_surface, (0, 0))
                else:
                    self.screen.fill((0, 0, 0))

            # Draw overlay
            self.draw_overlay()

            pygame.display.flip()

            now = time.time()
            delta = now - self.last_fps_time
            if delta > 0:
                current_fps = 1.0 / delta
                self.fps = self.fps_alpha * self.fps + (1.0 - self.fps_alpha) * current_fps
            self.last_fps_time = now

            self.clock.tick(FRAMERATE)

        self.cleanup()

    def cleanup(self):
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    app = GStreamerVideoOverlay()
    app.run()

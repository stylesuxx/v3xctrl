from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time
import threading


class TestRunner(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.last_modified = {}  # Dictionary to track last modification times

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return  # Ignore directories & non-Python files

        with self.lock:
            current_time = time.time()
            last_time = self.last_modified.get(event.src_path, 0)

            # Only process if it hasn't been modified in the last 1 second
            if current_time - last_time < 1:
                return  # Ignore rapid duplicate events

            self.last_modified[event.src_path] = current_time  # Update modification time

            print(f"🔄 File changed: {event.src_path}, re-running tests...")
            subprocess.run(["pytest", "./tests"])

observer = Observer()
test_runner = TestRunner()  # ✅ Single instance

# ✅ Watch `./tests` and `./src`, avoiding duplicate test runs
observer.schedule(test_runner, path="./tests", recursive=True)
observer.schedule(test_runner, path="./src", recursive=True)
observer.start()

print("👀 Watching for file changes... Press Ctrl+C to exit.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
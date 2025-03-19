from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time


class TestRunner(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            print(f"🔄 File changed: {event.src_path}, re-running tests...")
            subprocess.run(["pytest", "./tests"])


observer = Observer()
observer.schedule(TestRunner(), path="./tests", recursive=True)
observer.schedule(TestRunner(), path="./src", recursive=True)
observer.start()

print("👀 Watching for file changes... Press Ctrl+C to exit.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()

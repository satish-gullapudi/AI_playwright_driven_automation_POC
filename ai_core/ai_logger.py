import os
from datetime import datetime

log_dir = os.path.join("ai_reports", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"ai_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

def log_info(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

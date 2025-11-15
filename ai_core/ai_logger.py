import logging
import os
from pathlib import Path
from datetime import datetime

log_dir = os.path.join("ai_reports", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"ai_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logger = logging.getLogger("ai_framework")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    fh = logging.FileHandler(log_file)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)

def log_info(msg: str):
    logger.info(msg)

def log_error(msg: str):
    logger.error(msg)

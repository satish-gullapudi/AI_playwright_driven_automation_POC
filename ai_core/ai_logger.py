import logging
import os
from pathlib import Path
from datetime import datetime

log_dir = os.path.join(str(Path.cwd()), "ai_reports", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"ai_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logger = logging.getLogger("ai_framework")
logger.setLevel(logging.DEBUG)
logger.propagate = False

if not logger.handlers:
    fh = logging.FileHandler(log_file, mode='w')
    ch = logging.StreamHandler()

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] (%(name)s) %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

def log_info(msg: str):
    logger.info(msg)

def log_error(msg: str):
    logger.error(msg)

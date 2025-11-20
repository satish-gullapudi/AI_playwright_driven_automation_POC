import os
from pathlib import Path
from dotenv import load_dotenv


def load_env_variables():
    env_path = os.path.join(str(Path.cwd()), "secrets.env")
    # print(env_path)
    load_dotenv(dotenv_path=env_path, override=True)
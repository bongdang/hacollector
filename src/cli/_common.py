import os
import sys

from dotenv import load_dotenv  # type: ignore

from common.utils import setup_logger
from tcphandler.appconf_tcphandler import MainConfig


_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


def load_app_config(verbose: bool = False) -> MainConfig:
    setup_logger("cli", level="debug" if verbose else "info")
    app_config = MainConfig()
    load_dotenv()
    app_config.load_env_values()
    return app_config

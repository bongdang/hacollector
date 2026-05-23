from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

from loguru import logger

__all__ = [
    "logger",
    "setup_logger",
    "set_partial_debug",
    "is_partial_debug",
    "publish_mqtt_msg",
    "mark_last_action",
    "read_last_action",
    "remove_marked_action",
    "check_marked_action",
]

_partial_debug = False


def set_partial_debug(enabled: bool = True) -> None:
    global _partial_debug
    _partial_debug = enabled


def is_partial_debug() -> bool:
    return _partial_debug

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss,SSS}</green> "
    "<level>{level: >8}</level>:"
    "[<cyan>{function}</cyan>:<cyan>{line}</cyan>] "
    "<level>{message}</level>"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss,SSS} "
    "{level: >8}:"
    "[{function}:{line}] "
    "{message}"
)

_LEVEL_ALIASES = {
    "info": "INFO",
    "debug": "DEBUG",
    "warn": "WARNING",
    "warning": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
}


def _normalize_level(level: str) -> str:
    return _LEVEL_ALIASES.get(level.lower(), "INFO")


def setup_logger(
    app_name: str,
    log_dir: pathlib.Path | None = None,
    file_name: str | None = None,
    level: str = "info",
) -> bool:
    """Configure loguru sinks for the application.

    - Replaces all existing sinks.
    - stderr sink uses the requested level with color.
    - File sink (if log_dir + file_name given) always captures DEBUG and rotates at 1 MB, keeps 10 files.
    Returns False if the file sink could not be prepared.
    """
    logger.remove()
    console_level = _normalize_level(level)
    logger.add(sys.stderr, format=_CONSOLE_FORMAT, level=console_level, colorize=True)

    if log_dir is None or not file_name:
        return True

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / file_name,
            format=_FILE_FORMAT,
            level="DEBUG",
            rotation="1 MB",
            retention=10,
            encoding="utf-8",
            enqueue=True,
        )
    except Exception as e:
        print(f"Error in preparing log. [{e}]", file=sys.stderr)
        return False

    logger.bind(app=app_name)
    return True


def publish_mqtt_msg(mqtt_client, topic, payload):
    mqtt_client.publish(topic, payload)


def mark_last_action(prefix: str, num: int, obj) -> str:
    tempf = tempfile.NamedTemporaryFile(prefix=prefix, suffix='.json', delete=False, mode='w', encoding='utf-8')
    try:
        json.dump({'num': num, 'obj': obj.__dict__}, tempf)
    except Exception:
        tempf.close()
        os.unlink(tempf.name)
        raise
    tempf.close()
    return tempf.name


def read_last_action(marked_file: str):
    try:
        with open(marked_file, 'r', encoding='utf-8') as inf:
            data = json.load(inf)
        num = data['num']
        obj = data['obj']
        if not isinstance(num, int) or not isinstance(obj, dict) or 'error' in obj:
            return (0, None)
        return (num, obj)
    except Exception:
        return (0, None)


def remove_marked_action(marked_name: str):
    os.unlink(marked_name)


def check_marked_action(prefix: str) -> str:
    tmp_dir = tempfile.gettempdir()
    files = [filename for filename in os.listdir(tmp_dir) if filename.startswith(prefix)]
    if len(files) > 0:
        return os.path.join(tmp_dir, files[0])
    else:
        return ""

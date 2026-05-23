import asyncio
import time

import config as cfg
from loguru import logger
from devices.wallpad import WallPad
from handlers.mqtt_handler import MqttHandler


class Hub:
    def __init__(self, mqtt_handler: MqttHandler, wallpad: WallPad) -> None:
        self.mqtt_handler: MqttHandler          = mqtt_handler
        self.wallpad: WallPad                   = wallpad
        self.devices: list                      = []

        self.last_check_time                    = time.monotonic()

    def add_devices(self, enabled: list):
        self.devices.extend(enabled)

    async def async_scan_thread(self) -> None:
        while True:
            if self.mqtt_handler.start_discovery:
                self.mqtt_handler.homeassistant_device_discovery(initial=True)

            if time.monotonic() > self.last_check_time + cfg.WALLPAD_SCAN_INTERVAL_TIME:
                now = time.monotonic()
                self.last_check_time = now
                try:
                    self.wallpad.scan_wallpad_devices(now)
                except Exception as e:
                    logger.debug(f"[reScan]Error [{e}]")

            await asyncio.sleep(cfg.RS485_WRITE_INTERVAL_SEC * 2)

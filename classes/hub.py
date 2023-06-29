from __future__ import annotations

import asyncio
import time

import config as cfg
from classes.kocom import KocomHandler
from classes.lgac485 import LGACPacketHandler
from classes.mqtt import MqttHandler
from classes.utils import Color, ColorLog
from classes.wallpad import WallPad


class Hub:
    def __init__(self, kocom_handler, aircon_handler, mqtt_handler, wallpad) -> None:
        self.kocom_handler: KocomHandler        = kocom_handler
        self.mqtt_handler: MqttHandler          = mqtt_handler
        self.aircon_handler: LGACPacketHandler  = aircon_handler
        self.wallpad: WallPad                   = wallpad
        self.devices: list                      = []

    def add_devices(self, enabled: list):
        self.devices.extend(enabled)

    async def async_scan_thread(self) -> None:
        color_log = ColorLog()
        while True:
            if self.mqtt_handler.start_discovery:
                self.mqtt_handler.homeassistant_device_discovery(initial=True)

            if self.kocom_handler.comm.is_passed_safty_interval():
                try:
                    self.aircon_handler.loop = asyncio.get_running_loop()
                except Exception as e:
                    color_log.log(f"scan loop is not set. err:{e}", Color.Yellow, ColorLog.Level.WARN)
                try:
                    now = time.monotonic()
                    self.wallpad.scan_wallpad_devices(now)
                    await self.aircon_handler.async_scan_aircons(now)
                except Exception as e:
                    color_log.log(f"[reScan]Error [{e}]", Color.Red, ColorLog.Level.DEBUG)

            await asyncio.sleep(cfg.RS485_WRITE_INTERVAL_SEC * 2)

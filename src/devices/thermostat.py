import json

import config as cfg
from loguru import logger
from consts import (DEVICE_THERMOSTAT, MQTT_MODE, MQTT_TARGET_TEMP,
                    PAYLOAD_FAN_ONLY, PAYLOAD_HEAT, PAYLOAD_OFF, DeviceType,
                    HeatMode)
from devices.basedevice import Device


class Thermostat(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.device             = DeviceType.THERMOSTAT
        self.name: str          = DEVICE_THERMOSTAT
        self.room_name: str     = room_name
        self.mode: HeatMode     = HeatMode.OFF
        self.current_temp: int  = cfg.INIT_TEMP
        self.target_temp: int   = cfg.INIT_TEMP
        self.scan.reset()

    def handle_mqtt(self, payload: str, cmd_str: str) -> None:
        logger.debug(f"from MQTT(THERMOSTAT) : cmd_str={cmd_str}, payload={payload}")
        if cmd_str != MQTT_MODE:
            self.target_temp = int(float(payload))
            self.mode = HeatMode.HEAT
        elif cmd_str == MQTT_MODE:
            self.mode = HeatMode(payload)

    def make_command_from_data(self) -> str:
        mode_string = PAYLOAD_FAN_ONLY if self.mode == HeatMode.FAN_ONLY else \
            PAYLOAD_HEAT if self.mode == HeatMode.HEAT else PAYLOAD_OFF
        data_dict = {
            MQTT_MODE: mode_string,
            MQTT_TARGET_TEMP: self.target_temp
        }
        return json.dumps(data_dict)

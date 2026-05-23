import json

import config as cfg
from loguru import logger
from consts import (DEVICE_FAN, MQTT_FAN_SPEED, MQTT_PRESET_MODE, MQTT_SET,
                    PAYLOAD_HIGH, PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_OFF,
                    PAYLOAD_ON, DeviceType, FanSpeed, State)
from devices.basedevice import Device


class Fan(Device):
    def __init__(self) -> None:
        super().__init__()
        self.device             = DeviceType.FAN
        self.name               = DEVICE_FAN
        self.mode: State        = State.OFF
        self.fan_mode: FanSpeed = FanSpeed.OFF
        self.scan.reset()

    def handle_mqtt(self, payload: str, cmd_str: str) -> None:
        if cmd_str == f'{MQTT_PRESET_MODE}_set':
            payload_dict = json.loads(payload)
            if type(payload_dict) is dict:
                value = payload_dict[MQTT_PRESET_MODE]
            else:
                value = payload
            self.fan_mode = FanSpeed(value)
            if self.fan_mode != FanSpeed.OFF:
                self.mode = State.ON
            else:
                self.mode = State.OFF
            # color_log.log(f"Preset Mode Command [{self.fan_mode}, {self.mode}]", Color.Green, ColorLog.Level.DEBUG)
        elif cmd_str == MQTT_SET:
            if payload == PAYLOAD_ON:
                self.fan_mode = FanSpeed(cfg.DEFAULT_SPEED)
                self.mode = State.ON
            elif payload == PAYLOAD_OFF:
                self.fan_mode = FanSpeed.OFF
                self.mode = State.OFF
            else:
                self.fan_mode = FanSpeed(payload)
                self.mode = State.OFF if self.fan_mode == FanSpeed.OFF else State.ON
        elif cmd_str == MQTT_FAN_SPEED:
            self.fan_mode = FanSpeed(cfg.DEFAULT_SPEED) if payload == PAYLOAD_ON else FanSpeed(PAYLOAD_OFF)
            self.mode = State.ON
        logger.debug(f"Handle _fan Command [{self.fan_mode}, {self.mode}]")

    def make_command_from_data(self) -> str:
        speed_string = PAYLOAD_LOW if self.fan_mode == FanSpeed.LOW else \
            PAYLOAD_MEDIUM if self.fan_mode == FanSpeed.MEDIUM else \
            PAYLOAD_HIGH if self.fan_mode == FanSpeed.HIGH else PAYLOAD_OFF
        data_dict = {
            MQTT_PRESET_MODE: speed_string
        }
        return json.dumps(data_dict)

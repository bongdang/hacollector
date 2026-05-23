from __future__ import annotations

import json

from loguru import logger
from consts import DEVICE_LIGHT, PAYLOAD_ON, DeviceType, State, SwitchState
from devices.basedevice import Device


class Light(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.device                         = DeviceType.LIGHT
        self.name: str                      = DEVICE_LIGHT
        self.room_name: str                 = room_name
        self.light_list: list[SwitchState]  = []

    def set_initial_state(self, light_count) -> None:
        self.scan.reset()
        for i in range(0, light_count + 1):
            self.add_light(DEVICE_LIGHT + str(i), State.OFF)

    def add_light(self, itemname: str, state) -> None:
        self.light_list.append(SwitchState(itemname, list([state])))           # don't forget tuple is mutable. so...

    def handle_mqtt(self, payload: str, sub_device_str: str, room_str: str) -> None:
        logger.debug(f">>>>Light Setting room={room_str}, lights={self.name}")
        for light_name, light_state in self.light_list:
            if light_name == sub_device_str:
                light_state[0] = State.ON if payload == PAYLOAD_ON else State.OFF
                logger.debug(f"Light({light_name}) is set to {light_state}")
                break

    def make_command_from_data(self) -> str:
        data_dict = {}
        for light_name, light_state in self.light_list:
            if light_state[0] == State.ON:
                data_dict[light_name] = PAYLOAD_ON
        return json.dumps(data_dict)

import json

from loguru import logger
from consts import (DEVICE_ELEVATOR, PAYLOAD_ON,
                    DeviceType, State)
from devices.basedevice import Device


class Elevator(Device):
    def __init__(self) -> None:
        super().__init__()
        self.device         = DeviceType.ELEVATOR
        self.name           = DEVICE_ELEVATOR
        self.state: State   = State.OFF
        self.scan.reset()

    def handle_mqtt(self, payload: str) -> bool:
        logger.debug(f"elevator command from HA, payload = {payload}")
        if payload == PAYLOAD_ON:
            self.state = State.ON
            return True
        else:
            self.state = State.OFF
            return False

    def make_command_from_data(self) -> str:
        # elevator command always call
        data_dict = {"elevator": "call"}
        return json.dumps(data_dict)

import json

from loguru import logger
from consts import DEVICE_GAS, PAYLOAD_OFF, PAYLOAD_ON, DeviceType, State
from devices.basedevice import Device


class Gas(Device):
    def __init__(self) -> None:
        super().__init__()
        self.device         = DeviceType.GAS
        self.name           = DEVICE_GAS
        self.state: State   = State.ON
        self.scan.reset()

    def handle_mqtt(self, payload: str) -> bool:
        if payload == PAYLOAD_ON:
            logger.info("[From HA]GAS Cannot Set to ON")
            return False
        else:
            self.state = State.OFF
        return True

    def make_command_from_data(self) -> str:
        # gas make always off
        data_dict = {"gas": "off"}
        return json.dumps(data_dict)

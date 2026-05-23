import json

from loguru import logger
from consts import DEVICE_PLUG, PAYLOAD_ON, DeviceType, State, SwitchState
from devices.basedevice import Device


class Plug(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.device                         = DeviceType.PLUG
        self.name: str                      = DEVICE_PLUG
        self.room_name: str                 = room_name
        self.plug_list: list[SwitchState]   = []

    def set_initial_state(self, plug_count) -> None:
        self.scan.reset()
        for i in range(0, plug_count + 1):
            self.add_plug(DEVICE_PLUG + str(i), State.ON)

    def add_plug(self, itemname: str, state) -> None:
        self.plug_list.append(SwitchState(itemname, list([state])))

    def handle_mqtt(self, payload: str, sub_device_str: str, room_str: str) -> None:
        logger.debug(f"From MQTT(Plugs) Setting room={room_str}, lights={self.name}")
        for plug_name, plug_state in self.plug_list:
            if plug_name == sub_device_str:
                plug_state[0] = State.ON if payload == PAYLOAD_ON else State.OFF
                break

    def make_command_from_data(self) -> str:
        data_dict = {}
        for plug_name, plug_state in self.plug_list:
            if plug_state[0] == State.ON:
                data_dict[plug_name] = PAYLOAD_ON
        return json.dumps(data_dict)

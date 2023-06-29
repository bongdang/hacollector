from __future__ import annotations

from classes.basicdevice import Device
from classes.utils import Color, ColorLog
from consts import (DEVICE_GAS, PAYLOAD_OFF, PAYLOAD_ON, Command, DeviceType,
                    State)


class Gas(Device):
    def __init__(self) -> None:
        super().__init__()
        self.device         = DeviceType.GAS
        self.name           = DEVICE_GAS
        self.state: State   = State.ON
        self.scan.reset()

    def make_rs485_packet(self, cmd: Command) -> bytes:
        new_packet = Device.PacketStruct()
        color_log = ColorLog()

        modified_cmd = Command.OFF if cmd != Command.CHECK else cmd
        if not self.make_device_basic_info(new_packet, self.device, DeviceType.WALLPAD, modified_cmd):
            color_log.log(f"Error in make {self.device} packet!", Color.Red, ColorLog.Level.WARN)

        packet = new_packet.get_full_bytes_packet()

        color_log = ColorLog()
        color_log.log(f"[Packet made - Gas] = {packet.hex()}", Color.Yellow, ColorLog.Level.DEBUG)
        return packet

    def handle_mqtt(self, payload: str) -> bool:
        if payload == PAYLOAD_ON:
            payload = PAYLOAD_OFF
            color_log = ColorLog()
            color_log.log("[From HA]GAS Cannot Set to ON", Color.Yellow)
            return False
        else:
            self.state = State.OFF
        return True

    class GasInput:
        def __init__(self) -> None:
            self.command: str | None    = None
            self.room_str: str          = ''

        def make_dict_data(self) -> dict:
            return {DEVICE_GAS: self.command}

    def parse(self, value_p: bytes, room_no: int) -> dict:
        gas = self.GasInput()
        gas.command = PAYLOAD_ON if self.state == State.ON else PAYLOAD_OFF
        return gas.make_dict_data()

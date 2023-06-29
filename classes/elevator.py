from __future__ import annotations

from classes.basicdevice import Device
from classes.utils import Color, ColorLog
from consts import (DEVICE_ELEVATOR, PAYLOAD_OFF, PAYLOAD_ON, Command,
                    DeviceType, State)


class Elevator(Device):
    def __init__(self) -> None:
        super().__init__()
        self.device         = DeviceType.ELEVATOR
        self.name           = DEVICE_ELEVATOR
        self.state: State   = State.OFF
        self.scan.reset()

    def make_rs485_packet(self, cmd: Command) -> bytes:
        new_packet = Device.PacketStruct()
        color_log = ColorLog()

        if cmd != Command.CHECK:
            make_ok = self.make_device_basic_info(new_packet, DeviceType.WALLPAD, self.device, Command.ON)
        else:
            make_ok = self.make_device_basic_info(new_packet, self.device, DeviceType.WALLPAD, Command.CHECK)
        if not make_ok:
            color_log.log(f"Error in make {self.device} packet!", Color.Red, ColorLog.Level.WARN)

        packet = new_packet.get_full_bytes_packet()
        color_log = ColorLog()
        color_log.log(f"[Packet made - Elevator] = {packet.hex()}", Color.Yellow, ColorLog.Level.DEBUG)
        return packet

    def handle_mqtt(self, payload: str) -> bool:
        color_log = ColorLog()
        color_log.log(f"elevator command from HA, payload = {payload}", Color.Yellow, ColorLog.Level.DEBUG)
        if payload == PAYLOAD_ON:
            self.state = State.ON
            return True
        else:
            self.state = State.OFF
            return False

    class ElevatorInput:
        def __init__(self) -> None:
            self.status = PAYLOAD_OFF
            self.room_str: str = ''

        def make_dict_data(self) -> dict:
            return {DEVICE_ELEVATOR: self.status}

    def parse(self, value_p: bytes, room_no: int) -> dict:
        elevator = self.ElevatorInput()
        return elevator.make_dict_data()

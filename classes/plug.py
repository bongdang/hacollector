from __future__ import annotations

from classes.basicdevice import Device, SwitchInput
from classes.utils import Color, ColorLog
from consts import (DEVICE_PLUG, PAYLOAD_ON, Command, DeviceType, State,
                    SwitchState)


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

    def make_rs485_packet(self, cmd: Command) -> bytes:
        new_packet = Device.PacketStruct()
        color_log = ColorLog()

        if not self.make_device_basic_info(new_packet, self.device, DeviceType.WALLPAD, cmd, self.room_name):
            color_log.log(f"Error in make {self.device} packet!", Color.Red, ColorLog.Level.WARN)

        if cmd != Command.CHECK:
            try:
                new_packet.value_array = 0
                for switch_state in self.plug_list:
                    plug_num = int(switch_state.name.lstrip(DEVICE_PLUG))
                    if plug_num == 0:      # 0 is special meaning for all plug
                        continue
                    color_log.log(
                        f'n={switch_state.name}, s={switch_state.statelist[0]}',
                        Color.White,
                        ColorLog.Level.DEBUG
                    )
                    if switch_state.statelist[0] == State.ON:
                        pad = 0xff
                        pad = pad << (8 - plug_num) * 8
                        new_packet.value_array |= pad
                color_log.log(f"Plugs Set Data = [{new_packet.value_array:016x}]", Color.White, ColorLog.Level.DEBUG)
            except Exception as e:
                color_log.log(f"[Make Packet] Error({e}) on DeviceType.LIGHT", Color.White, ColorLog.Level.DEBUG)

        packet = new_packet.get_full_bytes_packet()

        color_log.log(f"[Packet made - light] = {packet.hex()}", Color.White, ColorLog.Level.DEBUG)
        return packet

    def handle_mqtt(self, payload: str, sub_device_str: str, room_str: str) -> None:
        color_log = ColorLog()
        color_log.log(
            f"From MQTT(Plugs) Setting room={room_str}, lights={self.name}",
            Color.White,
            ColorLog.Level.DEBUG
        )
        for plug_name, plug_state in self.plug_list:
            if plug_name == sub_device_str:
                plug_state[0] = State.ON if payload == PAYLOAD_ON else State.OFF
                break

    class PlugInput(SwitchInput):
        def __init__(self) -> None:
            super().__init__()

    def parse(self, value_p: bytes, room_no: int) -> dict:
        on_count = 0

        counts = 0
        switch = self.PlugInput()
        device_name = DEVICE_PLUG
        room_name = self.parse_kocom_room(f'{room_no:02d}')
        counts = self.parse_kocom_plug_size(room_name)

        # logger.debug(f'Room count of {self.source_device}:{counts}')
        for i in range(0, counts):
            if value_p[i] != 0x00:
                state = State.ON
                on_count += 1
            else:
                state = State.OFF
            switch.add_switch(device_name + str(i + 1), state)

        all_switch_state = State.ON if on_count > 0 else State.OFF
        switch.add_switch(device_name + str('0'), all_switch_state)
        return switch.make_dict_data()

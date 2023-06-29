from __future__ import annotations

from enum import Enum
from struct import calcsize, pack, unpack
from typing import Union

from classes.utils import Color, ColorLog
from config import (KOCOM_LIGHT_SIZE, KOCOM_PLUG_SIZE, KOCOM_ROOM,
                    KOCOM_ROOM_THERMOSTAT)
from consts import (DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS, DEVICE_LIGHT,
                    DEVICE_PLUG, DEVICE_THERMOSTAT, DEVICE_WALLPAD,
                    PAYLOAD_OFF, PAYLOAD_ON, Command, DeviceType, State)


class Device:
    class PacketStruct:
        HEADER_MAGIC    = b'\xaa\x55'
        DEFAULT_TYPESEQ = b'\x30\xbc\x00'
        PREFIX          = HEADER_MAGIC + DEFAULT_TYPESEQ
        POSTFIX         = b'\x0d\x0d'
        # FMT_type__seq   = 'H'
        # FMT_dummy       = 'B'
        # FMT_dst_device  = 'B'
        # FMT_dst_room    = 'B'
        # FMT_src_device  = 'B'
        # FMT_src_room    = 'B'
        # FMT_command     = 'B'
        # FMT_parameter   = 'Q'
        # FMT_checksum    = 'B'
        # FMT_one_packet  = '>' + FMT_type__seq    \
        #                     + FMT_dummy          \
        #                     + FMT_dst_device     \
        #                     + FMT_dst_room       \
        #                     + FMT_src_device     \
        #                     + FMT_src_room       \
        #                     + FMT_command        \
        #                     + FMT_parameter      \
        #                     + FMT_checksum
        FMT_one_packet  = '>HBBBBBBQB'

        def __init__(self) -> None:
            self.type_and_sequence: int = 0
            self.dummy: int             = 0
            self.dest_device_id: int    = 0
            self.dest_room_no: int      = 0
            self.src_device_id: int     = 0
            self.src_room_no: int       = 0
            self.command: int           = 0
            self.value_array: int       = 0
            self.checksum: int          = 0

        @property
        def _body_size(self) -> int:
            return calcsize(Device.PacketStruct.FMT_one_packet)

        def calc_checksum(self, body: Union[bytes, bytes]):
            checksum = sum(body)
            return checksum & 0xff

        def match_data(self, data) -> bool:
            try:
                if len(data) != self._body_size:
                    color_log = ColorLog()
                    color_log.log(
                        f"Error: Kocom Packet size mismatch {len(data)} != {self._body_size}",
                        Color.Red,
                        ColorLog.Level.DEBUG
                    )
                    return False
                res = unpack(Device.PacketStruct.FMT_one_packet, data)
                (
                    self.type_and_sequence,
                    self.dummy,
                    self.dest_device_id,
                    self.dest_room_no,
                    self.src_device_id,
                    self.src_room_no,
                    self.command,
                    self.value_array,
                    self.checksum
                ) = res
            except Exception as e:
                color_log = ColorLog()
                color_log.log(f"Error: unpack data = [{e}]", Color.Red, ColorLog.Level.DEBUG)
                return False
            return True

        def get_full_bytes_packet(self) -> bytes:
            try:
                pre_packet = pack(
                    Device.PacketStruct.FMT_one_packet,
                    self.type_and_sequence,
                    self.dummy,
                    self.dest_device_id,
                    self.dest_room_no,
                    self.src_device_id,
                    self.src_room_no,
                    self.command,
                    self.value_array,
                    0
                )
                chksum = self.calc_checksum(self.DEFAULT_TYPESEQ + pre_packet[3:-1])
                all_body = self.PREFIX + pre_packet[3:-1] + chksum.to_bytes(1, 'big') + self.POSTFIX
            except Exception as e:
                color_log = ColorLog()
                color_log.log(f"Error: unpack data = [{e}]", Color.Red, ColorLog.Level.DEBUG)
                return b''
            return all_body

    class ScanInfo:
        def __init__(self) -> None:
            self.reset()

        def reset(self) -> None:
            self.tick: float = 0.

    def __init__(self) -> None:
        self.scan = Device.ScanInfo()

    DEVICE_MAP = {
        DeviceType.WALLPAD: DEVICE_WALLPAD,
        DeviceType.LIGHT: DEVICE_LIGHT,
        DeviceType.THERMOSTAT: DEVICE_THERMOSTAT,
        DeviceType.PLUG: DEVICE_PLUG,
        DeviceType.ELEVATOR: DEVICE_ELEVATOR,
        DeviceType.GAS: DEVICE_GAS,
        DeviceType.FAN: DEVICE_FAN
    }

    KOCOM_DEVICE = {
        0x01: DeviceType.WALLPAD,
        0x0e: DeviceType.LIGHT,
        0x36: DeviceType.THERMOSTAT,
        0x3b: DeviceType.PLUG,
        0x44: DeviceType.ELEVATOR,
        0x2c: DeviceType.GAS,
        0x48: DeviceType.FAN
    }

    KOCOM_COMMAND = {
        0x3a: Command.CHECK,
        0x00: Command.STATUS,
        0x01: Command.ON,
        0x02: Command.OFF
    }
    KOCOM_DEVICE_REV           = {v: k for k, v in KOCOM_DEVICE.items()}
    KOCOM_COMMAND_REV          = {v: k for k, v in KOCOM_COMMAND.items()}
    KOCOM_ROOM_REV             = {v: k for k, v in KOCOM_ROOM.items()}
    KOCOM_ROOM_THERMOSTAT_REV  = {v: k for k, v in KOCOM_ROOM_THERMOSTAT.items()}

    @classmethod
    def match_kocom_device(cls, id: DeviceType) -> str:
        ret_str = cls.DEVICE_MAP.get(id)
        return ret_str if ret_str is not None else ''

    @classmethod
    def parse_kocom_device(cls, dev_hex: int) -> DeviceType | None:
        ret_enum = cls.KOCOM_DEVICE.get(dev_hex)
        return ret_enum if ret_enum is not None else None

    @classmethod
    def parse_kocom_command(cls, cmd_hex: int) -> Command | None:
        ret_enum = cls.KOCOM_COMMAND.get(cmd_hex)
        return ret_enum if ret_enum is not None else None

    @classmethod
    def parse_kocom_room(cls, strnum: str) -> str:
        ret_str = KOCOM_ROOM.get(strnum)
        return ret_str if ret_str is not None else ''

    @classmethod
    def parse_kocom_room_thermo(cls, strnum: str) -> str:
        ret_str = KOCOM_ROOM_THERMOSTAT.get(strnum)
        return ret_str if ret_str is not None else ''

    def get_kocom_device_data(self, id: DeviceType) -> int | None:
        return self.KOCOM_DEVICE_REV.get(id)

    def get_kocom_command_data(self, id: Command) -> int | None:
        return self.KOCOM_COMMAND_REV.get(id)

    def parse_kocom_light_size(self, strnum: str) -> int:
        ret_num = KOCOM_LIGHT_SIZE.get(strnum)
        return ret_num if ret_num is not None else 0

    def parse_kocom_plug_size(self, strnum: str) -> int:
        ret_num = KOCOM_PLUG_SIZE.get(strnum)
        return ret_num if ret_num is not None else 0

    def get_kocom_room_data(self, instr: str) -> str:
        ret_str = self.KOCOM_ROOM_REV.get(instr)
        return ret_str if ret_str is not None else ''

    def get_kocom_room_thermo_data(self, instr: str) -> str:
        ret_str = self.KOCOM_ROOM_THERMOSTAT_REV.get(instr)
        return ret_str if ret_str is not None else ''

    def make_device_basic_info(self,
                               new_packet: PacketStruct,
                               dest_devtype: DeviceType,
                               src_devtype: DeviceType,
                               cmd: Command,
                               room_name: str = '') -> bool:
        dest_device_id = self.get_kocom_device_data(dest_devtype)
        src_device_id = self.get_kocom_device_data(src_devtype)
        command = self.get_kocom_command_data(cmd)

        if dest_device_id is not None and src_device_id is not None and command is not None:
            new_packet.dest_device_id = dest_device_id
            new_packet.src_device_id = src_device_id
            new_packet.command = command
            if room_name != '':
                new_packet.dest_room_no = int(self.get_kocom_room_data(room_name))
            return True
        else:
            return False


class SwitchInput:
    class StatePair:
        def __init__(self, name: str, state: Enum) -> None:
            self.name = name
            self.state = state

    def __init__(self) -> None:
        self.switch_list: list[SwitchInput.StatePair] = []
        self.room_str: str = ''

    def add_switch(self, name: str, state: State) -> None:
        switch = SwitchInput.StatePair(name, state)
        self.switch_list.append(switch)

    def make_dict_data(self) -> dict:
        switch_dict = {}
        for switch in self.switch_list:
            assert isinstance(switch, SwitchInput.StatePair)
            if switch.state == State.ON:
                switch_dict[switch.name] = PAYLOAD_ON
            else:
                switch_dict[switch.name] = PAYLOAD_OFF
        return switch_dict

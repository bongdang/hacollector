from __future__ import annotations

import asyncio
import sys
from typing import Union

import config as cfg
from classes.appconf import MainConfig
from classes.basicdevice import Device
from classes.comm import TCPComm
from classes.elevator import Elevator
from classes.fan import Fan
from classes.gas import Gas
from classes.light import Light
from classes.plug import Plug
from classes.thermostat import Thermostat
from classes.utils import Color, ColorLog
from classes.wallpad import WallPad
from config import PACKET_RESEND_INTERVAL_SEC
from consts import (DEVICE_FAN, DEVICE_SENSOR, DEVICE_WALLPAD, Command,
                    CommStatus, DeviceType, HeaderMark, HeaderType, PacketType)


class KocomPacket:
    class ParsedInfo:
        def __init__(self, struct: Device.PacketStruct) -> None:
            self.reset_info()
            self.struct: Device.PacketStruct = struct

        def reset_info(self) -> None:
            self.device_id: DeviceType | None           = None
            self.room_str: str                          = ''
            self.type: PacketType                       = PacketType.ACK
            self.sequence: int                          = 0
            self.command: Command | None                = None
            self.source_device: DeviceType | None       = None
            self.source_room_no: int                    = 0
            self.destination_device: DeviceType | None  = None
            self.destination_room_no: int               = 0
            self.parsed_dict: dict                      = {}
            self.is_swapped                             = False

        def check_type_and_sequence(self):
            color_log = ColorLog()
            if (self.struct.type_and_sequence & 0xff00) == 0x3000:
                type_mask = self.struct.type_and_sequence & 0x00f0
                if type_mask == 0xb0:
                    self.type = PacketType.SEND
                elif type_mask == 0xd0:
                    self.type = PacketType.ACK
                else:
                    color_log.log(f"Unknown Packet Type! [0x{type_mask:02x}]", Color.Red, ColorLog.Level.WARN)
                    return False
                self.sequence = (self.struct.type_and_sequence & 0x000f) - 0x0c
                return True
            else:
                if ((self.struct.type_and_sequence & 0xff00) >> 8) in [x.b2 for x in KocomHandler.HEADER_LIST]:
                    if cfg.ALTERNATIVE_HEADER_DEBUG:
                        color_log.log(
                            f"[{self.struct.type_and_sequence:04x}] temporary passed!",
                            Color.Yellow,
                            ColorLog.Level.WARN
                        )
                    self.type = PacketType.ACK
                    self.sequence = 0
                    return True
                color_log.log(
                    f"Must not be HERE. Unknown Packet ***** [{self.struct.type_and_sequence:04x}]",
                    Color.Yellow,
                    ColorLog.Level.WARN
                )
                return False

        def parse_basic_info(self):
            self.command = Device.parse_kocom_command(self.struct.command)
            self.source_device = Device.parse_kocom_device(self.struct.src_device_id)
            self.source_room_no = self.struct.src_room_no
            self.destination_device = Device.parse_kocom_device(self.struct.dest_device_id)
            self.destination_room_no = self.struct.dest_room_no

        def is_ack_when_check(self) -> bool:
            if self.command == Command.CHECK and self.type == PacketType.ACK:
                return True
            return False

        def is_sending_to_elevator(self) -> bool:
            if self.type == PacketType.SEND and self.destination_device == DeviceType.ELEVATOR:
                return True
            return False

        def is_ack_to_wallpad(self) -> bool:
            if self.type == PacketType.ACK and self.destination_device == DeviceType.WALLPAD:
                return True
            return False

        def is_ack_from_wallpad(self) -> bool:
            if self.type == PacketType.ACK and self.source_device == DeviceType.WALLPAD:
                return True
            return False

        def is_fake_device_for_fan(self) -> bool:
            if self.source_device == self.destination_device:
                return True
            return False

        def swap_if_need_condition(self) -> None:
            if self.is_ack_from_wallpad():
                self.source_device, self.destination_device = self.destination_device, self.source_device
                self.source_room_no, self.destination_room_no = self.destination_room_no, self.source_room_no
                color_log = ColorLog()
                color_log.log(
                    f"Parse after swap src/dest"
                    f"(type={self.type}, cmd={self.command}, src={self.source_device}, dest={self.destination_device})",
                    Color.Magenta,
                    ColorLog.Level.DEBUG
                )
                self.is_swapped = True

        def parse_devices(self, input_8bytes: bytes) -> None:
            self.parsed_dict = {}
            dev: Union[Fan, Gas, Light, Plug, Elevator, Thermostat]
            if self.source_device == DeviceType.FAN:
                dev = Fan()
            elif self.source_device == DeviceType.LIGHT:
                dev = Light()
            elif self.source_device == DeviceType.PLUG:
                dev = Plug()
            elif self.source_device == DeviceType.THERMOSTAT:
                dev = Thermostat()
            elif self.source_device == DeviceType.GAS:
                dev = Gas()
            elif self.source_device == DeviceType.WALLPAD and self.destination_device == DeviceType.ELEVATOR:
                dev = Elevator()
            else:
                color_log = ColorLog()
                color_log.log(
                    f"MUST NOT BE HERE!! or just Elevator "
                    f"({input_8bytes.hex()}, {self.source_device}, {self.destination_device}, {self.type})",
                    Color.Red,
                    ColorLog.Level.DEBUG
                )
                return

            if self.source_device != self.destination_device:
                self.parsed_dict = dev.parse(input_8bytes, self.source_room_no)
            else:
                if type(dev) == Fan:
                    self.parsed_dict = dev.parse_sensor(input_8bytes, self.source_room_no)
            color_log = ColorLog()
            color_log.log(f"parsed Result = ({self.parsed_dict})", Color.Blue, ColorLog.Level.DEBUG)

        def make_parsed_info(self) -> None:
            self.room_str = ''
            color_log = ColorLog()
            try:
                color_log.log(f"make_parsed_info: input = {self.parsed_dict}", Color.Yellow, ColorLog.Level.DEBUG)
                color_log.log(
                    f"=>: t={self.type}, c={self.command}, s={self.source_device}, d={self.destination_device}",
                    Color.Yellow,
                    ColorLog.Level.DEBUG
                )
                self.device_id = self.source_device
                if self.is_sending_to_elevator():
                    self.device_id = self.destination_device
                    self.room_str = DEVICE_WALLPAD
                elif self.is_ack_to_wallpad() and self.is_swapped:
                    if self.source_device in [DeviceType.FAN, DeviceType.GAS, DeviceType.ELEVATOR]:
                        self.room_str = DEVICE_WALLPAD
                    elif self.source_device in [DeviceType.LIGHT, DeviceType.PLUG]:
                        self.room_str = Device.parse_kocom_room(f'{self.source_room_no:02d}')
                    elif self.source_device == DeviceType.THERMOSTAT:
                        self.room_str = Device.parse_kocom_room_thermo(f'{self.source_room_no:02d}')
                    else:
                        room = Device.parse_kocom_room(f'{self.source_room_no:02d}')
                        roomdest = Device.parse_kocom_room(f'{self.destination_room_no:02d}')
                        color_log.log(f"src room [{room}], dest rooom [{roomdest}]", Color.Yellow, ColorLog.Level.DEBUG)

                if self.room_str == '':
                    color_log.log(
                        f"No Data to Send!! "
                        f"t={self.type}, c={self.command}, s={self.source_device}, did={self.device_id}, "
                        f"d={self.destination_device}, room=[{self.destination_room_no}]",
                        Color.Yellow,
                        ColorLog.Level.DEBUG
                    )
                    return

                # current call 3
                # when Send : dest elevator, wallpad, val:
                # when ACK : src fan or gas, wallpad, val :
                # when ACK : src themo or light or plug, room, val
                color_log.log(
                    f"[From Kocom]{self.device_id}/{self.room_str}/state = {self.parsed_dict}",
                    Color.White,
                    ColorLog.Level.DEBUG
                )
            except Exception as e:
                color_log.log(f"Error in make_parsed_info [{e}]", Color.Red, ColorLog.Level.DEBUG)

    def __init__(self, rawdata: bytes = b'') -> None:
        self.struct = Device.PacketStruct()
        self.parsed = KocomPacket.ParsedInfo(self.struct)
        if rawdata != b'':
            self.struct.match_data(rawdata)

    def parse_data_from_packet(self) -> tuple[bool, str, str, dict]:
        color_log = ColorLog()

        # 0. Reset Previous parsed info.
        self.parsed.reset_info()
        try:
            # 1. Check Type
            if self.parsed.check_type_and_sequence():
                # 2. parse command, src/dst device and room no.
                self.parsed.parse_basic_info()

                # 3. ignore no need state
                if self.parsed.is_ack_when_check():
                    color_log.log("Just Ack from CHECK! - OK", Color.White, ColorLog.Level.DEBUG)
                else:
                    color_log.log(f"parse: input(v={self.struct.value_array:016x})", Color.White, ColorLog.Level.DEBUG)
                    color_log.log(
                        f"Parse: making data start.(type={self.parsed.type}, cmd={self.parsed.command}, "
                        f"src={self.parsed.source_device}, dest={self.parsed.destination_device})",
                        Color.White,
                        ColorLog.Level.DEBUG
                    )

                    # 3. src <-> dst some case.
                    self.parsed.swap_if_need_condition()
                    # 4. parse each devices
                    value_list = self.struct.value_array.to_bytes(8, 'big')
                    self.parsed.parse_devices(value_list)
                    # 5. get device, room, command string
                    self.parsed.make_parsed_info()
                    if isinstance(self.parsed.device_id, DeviceType):
                        if self.parsed.is_fake_device_for_fan():
                            device_str = DEVICE_SENSOR
                        else:
                            device_str = Device.match_kocom_device(self.parsed.device_id)
                        room_str = self.parsed.room_str
                        value = self.parsed.parsed_dict
                    else:
                        device_str = ''
                        room_str = ''
                        value = {}
                    return (True, device_str, room_str, value)
        except Exception as e:
            color_log.log(f"Packet parsing error [{e}] >>>>>>>>>>>", Color.Red, ColorLog.Level.DEBUG)

        return (False, '', '', {})

    def __repr__(self) -> str:
        packets = self.struct.get_full_bytes_packet()
        return str(packets.hex())


class KocomHandler:

    KOCOM_PACKET_LENGTH = 21
    # next header list is for unidentified header but has informations.
    HEADER_LIST = (
        HeaderMark('Main', 0xaa, 0x55, 17),
        HeaderMark('D555', 0xd5, 0x55, 16),
        HeaderMark('B515', 0xb5, 0x15, 16),
        HeaderMark('ABC1', 0xab, 0xc1, 16),
        HeaderMark('5530', 0x55, 0x30, 16),
        HeaderMark('D530', 0xd5, 0x30, 16),
        HeaderMark('D515', 0xd5, 0x15, 16),
        HeaderMark('5515', 0x55, 0x15, 16),
        HeaderMark('AD05', 0xad, 0x05, 16),
        HeaderMark('55E2', 0x55, 0xe2, 15),
        HeaderMark('55EA', 0x55, 0xea, 15),
    )
    FOOTER_1st_BYTE = 0x0d
    FOOTER_2nd_BYTE = 0x0d

    def __init__(self, config: MainConfig) -> None:
        self.name           = config.kocom_devicename
        self.enabled_dev    = []
        self.commstat       = CommStatus.WAIT_HEAD
        self.wallpad        = WallPad()
        self.comm: TCPComm  = TCPComm(
            config.kocom_server,
            int(config.kocom_port),
            cfg.MAX_SOCKET_BUFFER,
            cfg.PACKET_RESEND_INTERVAL_SEC
        )

        for dev in [
            DeviceType.THERMOSTAT.value,
            DeviceType.ELEVATOR.value,
            DeviceType.FAN.value,
            DeviceType.GAS.value,
            DeviceType.LIGHT.value,
            DeviceType.PLUG.value
        ]:
            if config.is_device_enabled(dev):
                self.enabled_dev.append(DeviceType(dev))

        self.wallpad.prepare_enabled(self.enabled_dev)

    @classmethod
    async def async_init(cls, config: MainConfig):
        return cls(config)

    async def async_prepare_communication(self):
        await self.comm.async_make_connection()

    def is_checksum_ok(self, body: bytes) -> bool:
        checksum = sum(body[:-1])

        if body[-1] == (checksum & 0xff):
            return True
        else:
            return False

    def handle_chunk(self, header_type: HeaderType, chunk: bytes) -> str:
        color_log = ColorLog()
        packet = KocomPacket(chunk)

        noti_to_HA, device_str, room_str, payload_value = packet.parse_data_from_packet()
        if header_type == HeaderType.Alter1:
            if cfg.ALTERNATIVE_HEADER_DEBUG:
                color_log.log(
                    f"Alter Header : noti={noti_to_HA}, device={device_str}, room={room_str}, ",
                    #                f"payload={payload_value}"",
                    Color.Green,
                    ColorLog.Level.WARN
                )
            return device_str
        if noti_to_HA:
            try:
                if device_str != '':
                    assert isinstance(payload_value, dict)
                    payload_value_str = payload_value
                    self.wallpad.notify_to_homeassistant(device_str, room_str, payload_value_str)
                    color_log.log(f"Yes. {packet} in sent to HA.", Color.White, ColorLog.Level.DEBUG)
                    return device_str
            except Exception as e:
                color_log.log(f"Error [{e}]in handling packets [{chunk.hex()}]", Color.White, ColorLog.Level.DEBUG)
        else:
            color_log.log(f"ACK packet. So, Do Nothong!! packet={packet}", Color.White, ColorLog.Level.DEBUG)
            return device_str
        return ''

    async def async_make_kocom_data_and_send(
        self, device_obj: Union[Gas, Fan, Elevator, Thermostat, Light, Plug, Device], cmd: Command
    ):
        color_log = ColorLog()
        assert isinstance(device_obj, (Gas, Fan, Elevator, Thermostat, Light, Plug))

        color_log.log(f"Make kocom Data - Start{device_obj}", Color.Yellow, ColorLog.Level.DEBUG)
        full_packet: bytes = device_obj.make_rs485_packet(cmd)
        if len(full_packet) != 0:
            ok: bool = await self.comm.async_write_one_chunk(full_packet)
            if ok:
                color_log.log(f"Data sent to Kocom : {full_packet.hex}", Color.Yellow, ColorLog.Level.DEBUG)
            else:
                color_log.log(f"Writing to Kocom Fail: {full_packet.hex}", Color.Red, ColorLog.Level.CRITICAL)
        else:
            color_log.log("Make kocom Data - Fail!!!", Color.Red, ColorLog.Level.DEBUG)

    async def async_read_until_tail(self) -> tuple[str, bytes, bytes, bytes]:
        color_log = ColorLog()

        class Chunk:
            def __init__(self) -> None:
                self.reset()

            def reset(self):
                self.packet_len     = 0
                self.body_len       = 0
                self.prev_data      = b'\x00'
                self.head_packet    = b''
                self.body_packet    = b''
                self.res_packet     = b''
                self.header_name    = ''
                self.need_len       = KocomHandler.KOCOM_PACKET_LENGTH - 4      # 4 means 2 header, 2 footer

            def append(self, add):
                self.res_packet += add
                self.packet_len += 1

            def is_body_len_match(self):
                if self.body_len == self.need_len:
                    return True
                else:
                    return False

            def copy_body(self):
                self.body_packet = self.res_packet
                self.res_packet = b''

            def copy_head(self, name: str, len: int):
                self.header_name    = name
                self.need_len       = len
                self.head_packet    = self.res_packet[-2:]
                self.res_packet     = b''
                self.body_len       = 0

            def __repr__(self):
                return (
                    f"PL:{self.packet_len}, BL:{self.body_len}, RP:{self.res_packet.hex()}, "
                    f"HP:{self.head_packet.hex()}, BP:{self.body_packet.hex()}"
                )

        header_start = set((x.b1 for x in KocomHandler.HEADER_LIST))

        chunk = Chunk()

        while chunk.packet_len < KocomHandler.KOCOM_PACKET_LENGTH:
            peek_data = await self.comm.async_get_data_from_buffer(1)
            # if you want sync version socket read
            # peek_data = await self.reader.read(1)
            if peek_data == b'':        # myabe closed! or error
                color_log.log("Socket Error. So, Quitting... for socket clear.", Color.Red, ColorLog.Level.WARN)
                sys.exit(1)

            if chunk.packet_len == 0 and self.commstat == CommStatus.WAIT_HEAD and not (peek_data[0] in header_start):
                color_log.log(f"packet staring with {peek_data[0]:02x}. so, Skipping", Color.Blue, ColorLog.Level.DEBUG)
                continue

            chunk.append(peek_data)
            pair = (chunk.prev_data[0], peek_data[0])

            if pair == (KocomHandler.FOOTER_1st_BYTE, KocomHandler.FOOTER_2nd_BYTE):
                color_log.log(str(chunk), Color.Red, ColorLog.Level.DEBUG)
                if self.commstat != CommStatus.WAIT_TAIL:
                    color_log = ColorLog()
                    color_log.log(
                        f"********* Wrong Packet = [ {chunk.res_packet.hex()} ] ********",
                        Color.Yellow,
                        ColorLog.Level.WARN
                    )
                break

            if self.commstat == CommStatus.WAIT_HEAD:
                color_log.log(str(chunk), Color.Red, ColorLog.Level.DEBUG)
                for hdr in KocomHandler.HEADER_LIST:
                    if pair == (hdr.b1, hdr.b2):
                        color_log.log(f"Header Detected![{chunk.res_packet.hex()}]", Color.Yellow, ColorLog.Level.DEBUG)
                        chunk.copy_head(hdr.name, hdr.len)
                        self.commstat = CommStatus.WAIT_BODY
                        break
            elif self.commstat == CommStatus.WAIT_BODY:
                chunk.body_len += 1
                if chunk.is_body_len_match():
                    color_log.log(str(chunk), Color.Red, ColorLog.Level.DEBUG)
                    chunk.copy_body()
                    self.commstat = CommStatus.WAIT_TAIL

            chunk.prev_data = peek_data

        return chunk.header_name, chunk.head_packet, chunk.body_packet, chunk.res_packet

    async def async_get_one_chunk(self) -> tuple[HeaderType, bytes]:
        color_log = ColorLog()
        try:
            header_type = HeaderType.Normal
            while True:
                self.commstat = CommStatus.WAIT_HEAD
                (header_name, magic_word, body, postfix) = await self.async_read_until_tail()

                color_log.log(f"=== read prefix = [{magic_word.hex()}]. Starting ===", Color.Cyan, ColorLog.Level.DEBUG)
                if self.commstat != CommStatus.WAIT_TAIL:
                    color_log.log(f"Bad Header[{magic_word.hex()}]. so, re-reading.", Color.Red, ColorLog.Level.DEBUG)
                    continue

                if not self.is_checksum_ok(body):
                    if header_name != KocomHandler.HEADER_LIST[0].name:
                        special_case = False
                        # next check is adhoc.. TT.
                        if header_name == '5530' or header_name == 'D530':
                            alt_body = b'\x30' + body
                            special_case = True
                        elif header_name == '55E2':
                            alt_body = b'\x0c' + body
                        elif header_name == '55EA':
                            alt_body = b'\x0d' + body
                        else:
                            if body[0] == 0xdc:
                                alt_body = b'\x30' + body
                                special_case = True
                            elif body[0] == 0xe2:
                                alt_body = b'\xd5\x55' + body
                            else:
                                alt_body = magic_word + body

                        if self.is_checksum_ok(alt_body):
                            if special_case:
                                body = alt_body
                            elif header_name == '55E2' or header_name == '55EA':
                                body = b'\x55\x30' + body
                            else:
                                body = alt_body[1:]
                            color_log.log(f"Alt Header Detected! = [{header_name}]", Color.Blue, ColorLog.Level.DEBUG)
                        else:
                            if cfg.ALTERNATIVE_HEADER_DEBUG:
                                color_log.log(
                                    f"Alt Header CASE : Body checksum Error![{alt_body.hex()}] will retry Read.",
                                    Color.Yellow,
                                    ColorLog.Level.DEBUG
                                )
                            self.commstat = CommStatus.WAIT_HEAD
                            continue
                    else:
                        color_log.log(
                            f"Main Header : Body checksum Error![{body.hex()}] will retry Read.",
                            Color.Yellow,
                            ColorLog.Level.DEBUG
                        )
                        self.commstat = CommStatus.WAIT_HEAD
                        continue

                if (
                    len(postfix) == 2
                    and (postfix[0], postfix[1]) == (KocomHandler.FOOTER_1st_BYTE, KocomHandler.FOOTER_2nd_BYTE)
                ):
                    color_log.log(f"Valid input body=[{body.hex()}]", Color.Green, ColorLog.Level.DEBUG)
                    # self.last_accessed_time = time.monotonic() # this maybe fix delayed action state change! - KKS
                    if header_name != KocomHandler.HEADER_LIST[0].name:
                        header_type = HeaderType.Alter1
                else:
                    color_log.log(
                        f"Wired CASE : Body checksum ok But Wrong Tail![{postfix.hex()}]",
                        Color.Yellow,
                        ColorLog.Level.WARN
                    )
                    header_type = HeaderType.Undefined
                break
            return header_type, body
        except Exception as e:
            color_log.log(f"[Error Kocom rs485] : {e} : Cannot read Magic Word!", Color.Red, ColorLog.Level.WARN)
        return HeaderType.Error, b''

    def make_sensor_chunk(self, chunk: bytes) -> bytes:
        source_fan = Device.parse_kocom_device(chunk[5])
        if source_fan == DeviceType.FAN:
            temp_chunk = bytearray(chunk)
            temp_chunk[3] = temp_chunk[5]
            return bytes(temp_chunk)
        return chunk

    async def reconnect_socket(self):
        await self.comm.close_async_socket()
        await asyncio.sleep(3 * PACKET_RESEND_INTERVAL_SEC)
        await self.async_prepare_communication()

    def sync_close_socket(self, loop: asyncio.AbstractEventLoop):
        #        loop.run_until_complete(self.comm.close_async_socket())
        pass

    # main loop
    async def kocom_main_read_loop(self) -> None:
        while True:
            await self.comm.wait_safe_communication()
            (header_type, chunk) = await self.async_get_one_chunk()
            if chunk != b'':
                dev_str = self.handle_chunk(header_type, chunk)
                if dev_str == DEVICE_FAN:
                    # adhoc adding fansensor
                    chunk = self.make_sensor_chunk(chunk)
                    _ = self.handle_chunk(header_type, chunk)
            elif header_type == HeaderType.Error:
                '''
                Kopcom Socket Error Case
                '''
                await self.reconnect_socket()

    async def kocom_main_write_loop(self) -> None:
        while True:
            await asyncio.sleep(0.01)
            if not self.wallpad.command_queue.empty():
                (_, obj, command) = self.wallpad.command_queue.get()
                assert isinstance(obj, WallPad.QueueWraper)
                await self.async_make_kocom_data_and_send(obj.device, command)
                await asyncio.sleep(PACKET_RESEND_INTERVAL_SEC)

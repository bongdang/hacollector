import asyncio

import config as cfg
from loguru import logger
from config import PACKET_RESEND_INTERVAL_SEC
from consts import (DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_SENSOR, DEVICE_WALLPAD,
                    Command, CommStatus, DeviceType, DeviceTypeMatch,
                    HeaderMark, HeaderType, PacketType)
from tcphandler.appconf_tcphandler import MainConfig
from tcphandler.comm_tcp import TCPComm
from tcphandler.kocom_devices import Device, RS485DeviceHandler


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
            if (self.struct.type_and_sequence & 0xff00) == 0x3000:
                type_mask = self.struct.type_and_sequence & 0x00f0
                if type_mask == 0xb0:
                    self.type = PacketType.SEND
                elif type_mask == 0xd0:
                    self.type = PacketType.ACK
                else:
                    logger.warning(f"Unknown Packet Type! [0x{type_mask:02x}]")
                    return False
                self.sequence = (self.struct.type_and_sequence & 0x000f) - 0x0c
                return True
            else:
                if ((self.struct.type_and_sequence & 0xff00) >> 8) in [x.b2 for x in KocomHandler.HEADER_LIST]:
                    if cfg.ALTERNATIVE_HEADER_DEBUG:
                        logger.warning(f"[{self.struct.type_and_sequence:04x}] temporary passed!")
                    self.type = PacketType.ACK
                    self.sequence = 0
                    return True
                logger.warning(f"Must not be HERE. Unknown Packet ***** [{self.struct.type_and_sequence:04x}]")
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
                logger.debug(f"Parse after swap src/dest"
                    f"(type={self.type}, cmd={self.command}, src={self.source_device}, dest={self.destination_device})")
                self.is_swapped = True

        def parse_devices(self, input_8bytes: bytes) -> None:
            self.parsed_dict = {}

            rs48f5_device = RS485DeviceHandler(self.source_device, self.destination_device, self.type, self.source_room_no)

            self.parsed_dict = rs48f5_device.parse_packet(input_8bytes)

            logger.debug(f"parsed Result = ({self.parsed_dict})")

        def make_parsed_info(self) -> None:
            def local_parse_kocom_room(strnum: str) -> str:
                ret_str = cfg.KOCOM_ROOM.get(strnum)
                return ret_str if ret_str is not None else ''

            def local_parse_kocom_room_thermo(strnum: str) -> str:
                ret_str = cfg.KOCOM_ROOM_THERMOSTAT.get(strnum)
                return ret_str if ret_str is not None else ''

            self.room_str = ''
            try:
                logger.debug(f"make_parsed_info: input = {self.parsed_dict}")
                logger.debug(f"=>: t={self.type}, c={self.command}, s={self.source_device}, d={self.destination_device}")
                self.device_id = self.source_device
                if self.is_sending_to_elevator():
                    self.device_id = self.destination_device
                    self.room_str = DEVICE_WALLPAD
                elif self.is_ack_to_wallpad() and self.is_swapped:
                    if self.source_device in [DeviceType.FAN, DeviceType.GAS, DeviceType.ELEVATOR]:
                        self.room_str = DEVICE_WALLPAD
                    elif self.source_device in [DeviceType.LIGHT, DeviceType.PLUG]:
                        self.room_str = local_parse_kocom_room(f'{self.source_room_no:02d}')
                    elif self.source_device == DeviceType.THERMOSTAT:
                        self.room_str = local_parse_kocom_room_thermo(f'{self.source_room_no:02d}')
                    else:
                        room = local_parse_kocom_room(f'{self.source_room_no:02d}')
                        roomdest = local_parse_kocom_room(f'{self.destination_room_no:02d}')
                        logger.debug(f"src room [{room}], dest rooom [{roomdest}]")

                if self.room_str == '':
                    logger.debug(f"No Data to Send!! "
                        f"t={self.type}, c={self.command}, s={self.source_device}, did={self.device_id}, "
                        f"d={self.destination_device}, room=[{self.destination_room_no}]")
                    return

                # current call 3
                # when Send : dest elevator, wallpad, val:
                # when ACK : src fan or gas, wallpad, val :
                # when ACK : src themo or light or plug, room, val
                logger.debug(f"[From Kocom]{self.device_id}/{self.room_str}/state = {self.parsed_dict}")
            except Exception as e:
                logger.debug(f"Error in make_parsed_info [{e}]")

    def __init__(self, rawdata: bytes = b'') -> None:
        self.struct = Device.PacketStruct()
        self.parsed = KocomPacket.ParsedInfo(self.struct)
        if rawdata != b'':
            self.struct.match_data(rawdata)

    def parse_data_from_packet(self) -> tuple[bool, str, str, dict]:

        # 0. Reset Previous parsed info.
        self.parsed.reset_info()
        try:
            # 1. Check Type
            if self.parsed.check_type_and_sequence():
                # 2. parse command, src/dst device and room no.
                self.parsed.parse_basic_info()

                # 3. ignore no need state
                if self.parsed.is_ack_when_check():
                    logger.debug("Just Ack from CHECK! - OK")
                else:
                    logger.debug(f"parse: input(v={self.struct.value_array:016x})")
                    logger.debug(f"Parse: making data start.(type={self.parsed.type}, cmd={self.parsed.command}, "
                        f"src={self.parsed.source_device}, dest={self.parsed.destination_device})")

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
                            device_str = DeviceTypeMatch.match_kocom_device(self.parsed.device_id)
                        room_str = self.parsed.room_str
                        value = self.parsed.parsed_dict
                        if (len(room_str) == 0 and (device_str in [DEVICE_FAN, 
                                                                   DEVICE_SENSOR, 
                                                                   DEVICE_ELEVATOR])):
                            room_str = DEVICE_WALLPAD
                        if len(room_str) != 0:
                            return (True, device_str, room_str, value)

                        logger.debug(f"Fall to Fail!! - will not send. {device_str}, {value}, {room_str}")

        except Exception as e:
            logger.debug(f"Packet parsing error [{e}] >>>>>>>>>>>")

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
        self.commstat       = CommStatus.WAIT_HEAD
        self._loop: asyncio.AbstractEventLoop | None = None
        self.comm: TCPComm  = TCPComm(
            config.kocom_server,
            int(config.kocom_port),
            cfg.MAX_SOCKET_BUFFER,
            cfg.PACKET_RESEND_INTERVAL_SEC,
            read_timeout=60.0  # Kocom may have idle periods between packets
        )

    @classmethod
    async def async_init(cls, config: MainConfig):
        return cls(config)

    async def async_prepare_communication(self):
        self._loop = asyncio.get_running_loop()
        await self.comm.connect_async_socket()

    def is_checksum_ok(self, body: bytes) -> bool:
        checksum = sum(body[:-1])

        if body[-1] == (checksum & 0xff):
            return True
        else:
            return False

    def set_mqtt_handler(self, send_state_to_mqtt):
        self.notify_to_mqtt = send_state_to_mqtt

    def handle_chunk(self, header_type: HeaderType, chunk: bytes) -> str:
        packet = KocomPacket(chunk)

        noti_to_HA, device_str, room_str, payload_value = packet.parse_data_from_packet()
        if header_type == HeaderType.Alter1:
            if cfg.ALTERNATIVE_HEADER_DEBUG:
                logger.warning(f"Alter Header : noti={noti_to_HA}, device={device_str}, room={room_str}, ")
            return device_str
        if noti_to_HA:
            try:
                if device_str != '':
                    assert isinstance(payload_value, dict)
                    payload_value_str = payload_value
                    self.notify_to_mqtt(device_str, room_str, payload_value_str)
                    logger.debug(f"Yes. {packet} in sent to HA.")
                    return device_str
            except Exception as e:
                logger.debug(f"Error [{e}]in handling packets [{chunk.hex()}]")
        else:
            logger.debug(f"ACK packet. So, Do Nothong!! packet={packet}")
            return device_str
        return ''

    async def async_read_until_tail(self) -> tuple[str, bytes, bytes, bytes]:

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

        logger.debug(">>Read full packet from RS485 Start")
        while chunk.packet_len < KocomHandler.KOCOM_PACKET_LENGTH:
            peek_data = await self.comm.async_get_data_from_buffer(1)
            # if you want sync version socket read
            # peek_data = await self.reader.read(1)
            if peek_data == b'':        # Actual EOF - connection closed by remote
                if self.comm.connection_reset:
                    logger.warning("Connection closed/reset. Returning empty - will trigger reconnect.")
                else:
                    logger.warning("Unexpected empty read without reset flag")
                return chunk.header_name, chunk.head_packet, chunk.body_packet, chunk.res_packet

            if chunk.packet_len == 0 and self.commstat == CommStatus.WAIT_HEAD and peek_data[0] not in header_start:
                logger.debug(f"packet staring with {peek_data[0]:02x}. so, Skipping")
                continue

            chunk.append(peek_data)
            pair = (chunk.prev_data[0], peek_data[0])

            if pair == (KocomHandler.FOOTER_1st_BYTE, KocomHandler.FOOTER_2nd_BYTE):
                logger.debug(str(chunk))
                if self.commstat != CommStatus.WAIT_TAIL:
                    logger.warning(f"********* Wrong Packet = [ {chunk.res_packet.hex()} ] ********")
                break

            if self.commstat == CommStatus.WAIT_HEAD:
                logger.debug(str(chunk))
                for hdr in KocomHandler.HEADER_LIST:
                    if pair == (hdr.b1, hdr.b2):
                        logger.debug(f"Header Detected![{chunk.res_packet.hex()}]")
                        chunk.copy_head(hdr.name, hdr.len)
                        self.commstat = CommStatus.WAIT_BODY
                        break
            elif self.commstat == CommStatus.WAIT_BODY:
                chunk.body_len += 1
                if chunk.is_body_len_match():
                    logger.debug(str(chunk))
                    chunk.copy_body()
                    self.commstat = CommStatus.WAIT_TAIL

            chunk.prev_data = peek_data

        logger.debug(f"<<Read packet[{chunk.header_name}],[{chunk.head_packet.hex()}],"
                      f"[{chunk.body_packet.hex()}],[{chunk.res_packet.hex()}] from RS485 Done")

        return chunk.header_name, chunk.head_packet, chunk.body_packet, chunk.res_packet

    async def async_get_one_chunk(self) -> tuple[HeaderType, bytes]:
        try:
            header_type = HeaderType.Normal
            while True:
                self.commstat = CommStatus.WAIT_HEAD
                (header_name, magic_word, body, postfix) = await self.async_read_until_tail()

                if self.comm.connection_reset and magic_word == b'' and body == b'' and postfix == b'':
                    logger.warning("Detected closed/reset socket while reading packet - forcing reconnect path")
                    return HeaderType.Error, b''

                if magic_word == b'' and body == b'' and postfix == b'':
                    # Avoid tight loop on unexpected empty read without a reset signal.
                    await asyncio.sleep(0.1)
                    continue

                logger.debug(f"=== read prefix = [{magic_word.hex()}]. Starting ===")
                if self.commstat != CommStatus.WAIT_TAIL:
                    logger.debug(f"Bad Header[{magic_word.hex()}]. so, re-reading.")
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
                            logger.debug(f"Alt Header Detected! = [{header_name}]")
                        else:
                            if cfg.ALTERNATIVE_HEADER_DEBUG:
                                logger.debug(f"Alt Header CASE : Body checksum Error![{alt_body.hex()}] will retry Read.")
                            self.commstat = CommStatus.WAIT_HEAD
                            continue
                    else:
                        logger.debug(f"Main Header : Body checksum Error![{body.hex()}] will retry Read.")
                        self.commstat = CommStatus.WAIT_HEAD
                        continue

                if len(postfix) == 2 and \
                   (postfix[0], postfix[1]) == (KocomHandler.FOOTER_1st_BYTE, KocomHandler.FOOTER_2nd_BYTE):
                    logger.debug(f"Valid input body=[{body.hex()}]")
                    # self.last_accessed_time = time.monotonic() # this maybe fix delayed action state change! - KKS
                    if header_name != KocomHandler.HEADER_LIST[0].name:
                        header_type = HeaderType.Alter1
                else:
                    logger.warning(f"Wired CASE : Body checksum ok But Wrong Tail![{postfix.hex()}]")
                    header_type = HeaderType.Undefined
                break
            return header_type, body
        except Exception as e:
            logger.warning(f"[Error Kocom rs485] : {e} : Cannot read Magic Word!")
        return HeaderType.Error, b''

    def make_sensor_chunk(self, chunk: bytes) -> bytes:
        source_fan = Device.parse_kocom_device(chunk[5])
        if source_fan == DeviceType.FAN:
            temp_chunk = bytearray(chunk)
            temp_chunk[3] = temp_chunk[5]
            return bytes(temp_chunk)
        return chunk

    async def reconnect_socket(self):
        logger.info("Reconnecting Kocom socket...")

        try:
            # Reset connection state before reconnection
            self.comm.connection_reset = False
            
            await self.comm.close_async_socket()
            await asyncio.sleep(3 * PACKET_RESEND_INTERVAL_SEC)
            await self.async_prepare_communication()
            
            logger.info("Kocom reconnection completed successfully")
        except Exception as e:
            logger.error(f"Kocom reconnection failed: {e}")
            # Clear buffer to avoid stale data
            self.comm.read_buffer = b''
            raise

    def sync_close_socket(self, loop: asyncio.AbstractEventLoop):
        loop.run_until_complete(self.comm.close_async_socket())
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
                try:
                    await self.reconnect_socket()
                except Exception as e:
                    logger.error(f"Reconnect failed, retrying in 10s: {e}")
                    await asyncio.sleep(10)

    def tcp_send_handler(self, device_str: str, room_str: str, payload: str, command: Command) -> None:
        rs485_handler = RS485DeviceHandler(None, None, None, 0)         # means no need to parse

        try:
            made_packet: bytes = rs485_handler.make_packet(device_str, payload, command, room_str)
            if made_packet != b'':
                self.async_send_made_packet(made_packet)

        except Exception as e:
            logger.info(f"[MQTT to RS485]Error [{e}] {device_str}/{room_str} = {payload}")

    def async_send_made_packet(self, full_packet: bytes):
        if len(full_packet) == 0:
            logger.info("Make kocom Data - Fail!!!")
            return

        logger.debug(f"[Packet made] = {full_packet.hex()}")
        if self._loop is None:
            logger.warning("Event loop not ready, cannot send packet")
            return

        # Called from the paho callback thread. Submit the write to the event loop but do
        # NOT block on future.result() — that would stall paho's network thread (delaying
        # keepalive/PINGREQ and other inbound messages) for up to the write's
        # wait_safe_communication interval. async_write_one_chunk serializes writes via the
        # comm _write_lock, so writes never collide on the half-duplex bus. Result is logged
        # asynchronously via the done-callback (runs on the event-loop thread).
        future = asyncio.run_coroutine_threadsafe(
            self.comm.async_write_one_chunk(full_packet), self._loop
        )

        def _log_write_result(fut, pkt=full_packet):
            try:
                ok = fut.result()
            except Exception as e:
                logger.critical(f"Writing to Kocom Fail: {e} [{pkt.hex()}]")
                return
            if ok:
                logger.debug(f"Data sent to Kocom : {pkt.hex()}")
            else:
                logger.critical(f"Writing to Kocom Fail: {pkt.hex()}")

        future.add_done_callback(_log_write_result)

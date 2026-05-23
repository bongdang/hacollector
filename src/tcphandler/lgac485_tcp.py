import asyncio
import json
import os
# import sys
import time
# from queue import Queue
from struct import calcsize, pack, unpack
from typing import Callable

import config as cfg
from loguru import logger
from common.utils import mark_last_action, remove_marked_action, check_marked_action, read_last_action
from consts import (AIRCON_DEFAULT_TEMP, MQTT_FAN_MODE, MQTT_MODE,
                    MQTT_SWING_MODE, MQTT_TARGET_TEMP, PAYLOAD_AUTO,
                    PAYLOAD_COOL, PAYLOAD_DRY, PAYLOAD_FAN_ONLY, PAYLOAD_FIXED,
                    PAYLOAD_HEAT, PAYLOAD_HIGH, PAYLOAD_LOCKOFF, MQTT_CURRENT_TEMP,
                    PAYLOAD_LOCKON, PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_OFF,
                    PAYLOAD_ON, PAYLOAD_POWER, PAYLOAD_SCAN, PAYLOAD_SILENT,
                    PAYLOAD_STATUS, PAYLOAD_SWING, DeviceType)
from devices.aircon import Aircon
from tcphandler.appconf_tcphandler import MainConfig
from tcphandler.comm_tcp import TCPComm

TEST_LGAC_SERVER = '10.0.0.252'
TEST_LGAC_PORT = 8899

MAX_READ_ERROR_RETRY = 3
MAX_AIRCON_COMM_TIME = 3
MAX_MARKED_RETRY = 2  # Maximum retry attempts for marked actions
MARK_EXPIRY_SECONDS = 300  # 5 minutes

MARK_FILE_PREFIX = 'bd-aircon-'


class LGACPacket:
    _WRITER_HEADER_MAGIC    = b'\x80\x00\xa3'
    _RESPONSE_PACKET_SIZE   = 16
    # FMT_fill_return_head    = 'B'
    # FMT_action              = 'B'
    # FMT_fill_unknown1       = 'B'
    # FMT_fill_unknown2       = 'B'
    # FMT_groupandid          = 'B'
    # FMT_fill_unknown3       = 'B'
    # FMT_current_mode        = 'B'
    # FMT_set_temp            = 'B'
    # FMT_current_temp        = 'B'
    # FMT_pipe1_temp          = 'B'
    # FMT_pipe2_temp          = 'B'
    # FMT_fill_outer_sensor   = 'B'
    # FMT_fill_unknown4       = 'B'
    # FMT_fill_model          = 'B'
    # FMT_fill_fixedvalue     = 'B'
    # FMT_checksum            = 'B'
    # FMT_body_read           = '>' + \
    #                             FMT_fill_return_head    + \
    #                             FMT_action              + \
    #                             FMT_fill_unknown1       + \
    #                             FMT_fill_unknown2       + \
    #                             FMT_groupandid          + \
    #                             FMT_fill_unknown3       + \
    #                             FMT_current_mode        + \
    #                             FMT_set_temp            + \
    #                             FMT_current_temp        + \
    #                             FMT_pipe1_temp          + \
    #                             FMT_pipe2_temp          + \
    #                             FMT_fill_outer_sensor   + \
    #                             FMT_fill_unknown4       + \
    #                             FMT_fill_model          + \
    #                             FMT_fill_fixedvalue     + \
    #                             FMT_checksum
    FMT_body_read           = '>BBBBBBBBBBBBBBBB'
    FMT_body_write          = '>BBBB'

    LGAC_ACTION = {
        0x00: PAYLOAD_SCAN,
        0x01: PAYLOAD_STATUS,
        0x02: PAYLOAD_OFF,
        0x03: PAYLOAD_ON,
        0x06: PAYLOAD_LOCKON,
        0x07: PAYLOAD_LOCKOFF
    }
    LGAC_MODE = {
        0: PAYLOAD_COOL,
        1: PAYLOAD_DRY,
        2: PAYLOAD_FAN_ONLY,
        3: PAYLOAD_AUTO,      # PAYLOAD_AUTO, HA do not support auto
        4: PAYLOAD_HEAT
    }
    LGAC_FAN_SPEED = {
        1: PAYLOAD_LOW,
        2: PAYLOAD_MEDIUM,
        3: PAYLOAD_HIGH,
        4: PAYLOAD_AUTO,
        5: PAYLOAD_SILENT,
        6: PAYLOAD_POWER
    }
    LGAC_ACTION_REV        = {v: k for k, v in LGAC_ACTION.items()}
    LGAC_MODE_REV          = {v: k for k, v in LGAC_MODE.items()}
    LGAC_FAN_SPEED_REV     = {v: k for k, v in LGAC_FAN_SPEED.items()}

    def __init__(self, rawdata: bytes | None = None) -> None:
        self.fill_return_head    = 0
        self.action              = 0
        self.fill_unknown1       = 0
        self.fill_unknown2       = 0
        self.groupandid          = 0
        self.fill_unknown3       = 0
        self.current_mode        = 0
        self.set_temp            = 0
        self.current_temp        = 0
        self.pipe1_temp          = 0
        self.pipe2_temp          = 0
        self.fill_outer_sensor   = 0
        self.fill_unknown4       = 0
        self.fill_model          = 0
        self.fill_fixedvalue     = 0
        self.checksum            = 0
        self.str_action: str = ''
        self.str_opmode: str = ''
        self.str_fanmove: str = ''
        self.str_fanmode: str = ''
        if rawdata is not None:
            self.set_packet_data(rawdata)

    @property
    def _body_size(self) -> int:
        return calcsize(LGACPacket.FMT_body_read)

    def set_packet_data(self, rawdata: bytes) -> bool:
        try:
            if len(rawdata) != self._body_size:
                logger.debug(f"Error: LGAC Packet size mismatch {len(rawdata)} != {self._body_size}")
                return False
            res = unpack(LGACPacket.FMT_body_read, rawdata)
            (
                self.fill_return_head,
                self.action,
                self.fill_unknown1,
                self.fill_unknown2,
                self.groupandid,
                self.fill_unknown3,
                self.current_mode,
                self.set_temp,
                self.current_temp,
                self.pipe1_temp,
                self.pipe2_temp,
                self.fill_outer_sensor,
                self.fill_unknown4,
                self.fill_model,
                self.fill_fixedvalue,
                self.checksum
            ) = res
            self.set_temp = (self.set_temp & 0x0f) + 0x0f
            self.current_temp = cfg.TEMPERATURE_ADJUST + self.calc_temp(self.current_temp)
            self.pipe1_temp = self.calc_temp(self.pipe1_temp)
            self.pipe2_temp = self.calc_temp(self.pipe2_temp)
            self.get_detail_mode()
            logger.debug(f"LGAC Packet Body = [ {rawdata.hex()} ]")
            return True
        except Exception as e:
            logger.debug(f"Error: LGAC unpack data = [{e}]")
            return False

    def get_lgac_action_data(self, id: str) -> int:
        ret_int = self.LGAC_ACTION_REV.get(id)
        return ret_int if ret_int is not None else 0

    def parse_lgac_action(self, inbyte: int) -> str:
        ret_enum = self.LGAC_ACTION.get(inbyte)
        return ret_enum if ret_enum is not None else ''

    def get_lgac_mode_data(self, id: str) -> int:
        ret_int = self.LGAC_MODE_REV.get(id)
        return ret_int if ret_int is not None else 0

    def parse_lgac_mode(self, inbyte: int) -> str:
        ret_enum = self.LGAC_MODE.get(inbyte)
        return ret_enum if ret_enum is not None else ''

    def get_lgac_fanspeed_data(self, id: str) -> int:
        ret_int = self.LGAC_FAN_SPEED_REV.get(id)
        return ret_int if ret_int is not None else 0

    def parse_lgac_fanspeed(self, inbyte: int) -> str:
        ret_enum = self.LGAC_FAN_SPEED.get(inbyte)
        return ret_enum if ret_enum is not None else ''

    def make_new_packet(self, group, id, action, operation, fanmove, fanspeed, temp) -> None:
        self.groupandid = (group << 4) + id
        self.str_action = action
        self.str_opmode = operation
        self.str_fanmove = fanmove
        self.str_fanmode = fanspeed
        self.set_temp = temp - 0x0f if 18 <= temp <= 30 else 10
        self.set_detail_mode()

    def calc_temp(self, num: int) -> float:
        # maybe value was made from (36 - x) * 4 + 18 * 4.
        return round(54.0 - num / 4, 2)

    def get_detail_mode(self) -> None:
        self.str_action = self.parse_lgac_action(self.action)
        if self.str_action == '':
            self.str_action = PAYLOAD_STATUS

        self.str_opmode = self.parse_lgac_mode(self.current_mode & 0x07)

        # HA dose not support AUTO MODE
        if self.str_opmode == PAYLOAD_AUTO:
            self.str_opmode = PAYLOAD_COOL

        if self.current_mode & 0x08:
            self.str_fanmove = PAYLOAD_SWING
        else:
            self.str_fanmove = PAYLOAD_FIXED

        self.str_fanmode = self.parse_lgac_fanspeed((self.current_mode >> 4) & 0x07)
        if self.str_fanmode == '':
            self.str_fanmode = PAYLOAD_LOW
        if self.str_fanmode == PAYLOAD_AUTO:       # HA dose not support fan_mode auto
            self.str_fanmode = PAYLOAD_LOW

        logger.debug(f"LGAC new_packet = [{self}]")

    def set_detail_mode(self) -> None:
        self.action = self.get_lgac_action_data(self.str_action)

        opmode = self.get_lgac_mode_data(self.str_opmode)

        if self.str_fanmove == PAYLOAD_SWING:
            opmode |= 0x08
        mode = opmode

        fan_speed = self.get_lgac_fanspeed_data(self.str_fanmode)

        self.current_mode = mode | (fan_speed << 4) & 0xf0

    def __repr__(self) -> str:
        return (
            f"GroupandID:{self.groupandid}, action:{self.str_action}, "
            f"operation:{self.str_opmode}, fanmove:{self.str_fanmove}, "
            f"fanmode:{self.str_fanmode}, temp:{self.set_temp}, "
            f"currenttemp:{self.current_temp}, actemp1:{self.pipe1_temp}, actemp2:{self.pipe2_temp}"
        )

    def make_send_packet(self) -> bytes:
        def calc_checksum(body: bytes) -> int:
            checksum = sum(body)
            return (checksum & 0xff) ^ 0x55

        packet = bytes()
        packet += LGACPacket._WRITER_HEADER_MAGIC
        packet += pack(
            LGACPacket.FMT_body_write,
            self.groupandid,
            self.action,
            self.current_mode,
            self.set_temp
        )
        chksum = calc_checksum(packet)
        packet += chksum.to_bytes(1, 'big')
        return packet


class LGACPacketHandler:
    def __init__(self, config: MainConfig | None = None) -> None:
        self.SYSTEM_ROOM_AIRCON_REV = {v: k for k, v in cfg.SYSTEM_ROOM_AIRCON.items()}
        self.name                       = config.aircon_devicename if config is not None else 'TestAircon'
        self.enabled_device_list: list  = []
        self.aircon: list               = []
        self.type                       = None
        if config:
            self.comm: TCPComm              = TCPComm(
                config.aircon_server,
                int(config.aircon_port),
                cfg.MAX_SOCKET_BUFFER,
                cfg.PACKET_RESEND_INTERVAL_SEC
            )
        # self.command_queue: Queue       = Queue()
        self.loop: asyncio.AbstractEventLoop
        self.read_error_count           = 0
        self.send_and_get_state         = False
        self.send_start_time: float     = 0.0
        self.notify_to_homeassistant_aircon: Callable[[str, str, Aircon.Info], None] | None = None  # type: ignore
        self.notify_as_mqtt_aircon: Callable[[str, str, Aircon.Info], None] | None = None  # type: ignore
        self.prepare_enabled()

    def sync_close_socket(self, loop):
        pass

    def set_send_state(self, state: bool):
        self.send_and_get_state = state

    def check_aircon_communicationable_or_reset(self) -> bool:
        # use closure for easy reading.
        def reset_timer():
            self.send_start_time = 0.0

        def is_first_check() -> bool:
            if self.send_start_time == 0.0:
                return True
            return False

        def is_sending() -> bool:
            return self.send_and_get_state

        def set_start_time():
            self.send_start_time = time.monotonic()

        def time_passed_as_sec() -> float:
            return time.monotonic() - self.send_start_time

        if not is_sending():
            reset_timer()
            return True
        else:
            if is_first_check():
                set_start_time()
            elif time_passed_as_sec() > MAX_AIRCON_COMM_TIME:
                logger.critical(f"LGAC Communication timeout after {MAX_AIRCON_COMM_TIME}s - forcing reconnection")
                self.send_and_get_state = False
                self.send_start_time = 0.0
                raise RuntimeError("LGAC communication timeout - connection needs reset")

            return False

    def set_notify_to_homeassistant_aircon(self, change_aircon_status):
        self.notify_to_homeassistant_aircon: Callable[[str, str, Aircon.Info], None] = change_aircon_status

    def set_notify_as_mqtt_aircon(self, change_aircon_status):
        self.notify_as_mqtt_aircon: Callable[[str, str, Aircon.Info], None] = change_aircon_status

    def prepare_enabled(self):
        for r_name in cfg.SYSTEM_ROOM_AIRCON.values():
            aircon = Aircon(r_name)
            aircon.set_initial_state()
            self.aircon.append(aircon)
        self.enabled_device_list.append((DeviceType.AIRCON, self.aircon))

    def get_room_aircon_number(self, instr: str) -> str:
        ret_str = self.SYSTEM_ROOM_AIRCON_REV.get(instr)
        return ret_str if ret_str is not None else ''

    def get_aircon(self, room_name: str) -> Aircon:
        if self.aircon is not None and len(self.aircon) >= 1:
            for item in self.aircon:
                assert isinstance(item, Aircon)
                if item.room_name == room_name:
                    return item
        assert False, "get_aircon error!"

    def is_checksum_ok(self, body: bytes) -> bool:
        checksum = sum(body[:-1])

        if body[-1] == (checksum & 0xff) ^ 0x55:
            return True
        else:
            return False

    async def async_read_until_tail(self) -> bytes:
        packet_len = 0
        res_packet = bytes()
        while packet_len < LGACPacket._RESPONSE_PACKET_SIZE:
            peek_data = await self.comm.async_get_data_direct(1)
            if peek_data == b'':        # maybe closed!
                break
            res_packet += peek_data
            packet_len += 1
        return res_packet

    async def async_read_one_chunk(self) -> bytes | None:
        try:
            body = await self.async_read_until_tail()
            if len(body) != LGACPacket._RESPONSE_PACKET_SIZE:
                logger.debug("Packet size is not MATCH! - retry!")
                return None

            if not self.is_checksum_ok(body):
                logger.info(f"Unhappy CASE(Aircon) : Checksum Error![{body.hex()}]")
                logger.debug("trying to read again!! ******")
                return None

            return body

        except Exception as e:
            logger.warning(f"[Error LGAC rs485] : {e} : Cannot read From LGAC!")
        return None

    async def async_send_and_get_result(self, group_no: int, id: int, airconset: Aircon.Info, max_retries: int = 2) -> Aircon.Info | None:
        def handle_max_read_error():
            logger.critical(f"LGAC read failed {MAX_READ_ERROR_RETRY} times - connection unstable")
            raise RuntimeError(f"LGAC: Exceeded max read errors ({MAX_READ_ERROR_RETRY} failures)")

        self.set_send_state(True)

        packet = LGACPacket(None)
        packet.make_new_packet(
            group_no, id,
            airconset.action, airconset.opmode, airconset.fanmove, airconset.fanmode, airconset.target_temp
        )

        send_packet = packet.make_send_packet()

        ret: Aircon.Info | None = None
        retry_count = 0

        # need some wait
        while retry_count <= max_retries:
            try:
                # Force new connection on each attempt to handle RS485 WiFi device issues
                await self.comm.connect_async_socket()

                ok: bool = await self.comm.async_write_one_chunk(send_packet)
                if ok:
                    await asyncio.sleep(cfg.RS485_WRITE_INTERVAL_SEC)
                    read_packet = await self.async_read_one_chunk()
                    if read_packet:
                        logger.info(f"Read From LGAC ==> {read_packet.hex()}")

                        new_packet = LGACPacket(read_packet)
                        logger.debug(f'{new_packet}')

                        ret = Aircon.Info(
                            new_packet.str_action,
                            new_packet.str_opmode,
                            new_packet.str_fanmove,
                            new_packet.str_fanmode,
                            new_packet.current_temp,
                            new_packet.set_temp
                        )
                        self.read_error_count = 0
                        break  # Success, exit retry loop
                    else:
                        logger.info("Read From LGAC FAIL!")
                        self.read_error_count += 1
                        if self.read_error_count > MAX_READ_ERROR_RETRY:
                            self.read_error_count = 0
                            handle_max_read_error()
                else:
                    logger.info(f"Write to LGAC FAIL!{send_packet.hex()}")

                # Close connection before retry
                await self.comm.close_async_socket()
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(f"Retry attempt {retry_count}/{max_retries}...")
                    await asyncio.sleep(0.5)  # Wait before retry

            except Exception as e:
                logger.critical(f"Something wrong in Write and read Aircon({e})")
                await self.comm.close_async_socket()
                retry_count += 1
                if retry_count <= max_retries:
                    await asyncio.sleep(0.5)

        # Clean up connection after all attempts
        try:
            await self.comm.close_async_socket()
        except Exception:
            pass

        self.set_send_state(False)
        return ret

    async def async_get_current_status(self, aircon_no: int) -> Aircon.Info | None:
        aircon_cmd = Aircon.Info(PAYLOAD_STATUS, '', '', '', AIRCON_DEFAULT_TEMP, AIRCON_DEFAULT_TEMP)
        logger.info(f"Get Aircon Status : {aircon_no}")

        if self.check_aircon_communicationable_or_reset():
            # is_marked = check_marked_action(MARK_FILE_PREFIX)
            # if len(is_marked) != 0:
            #     no, cmd = read_last_action(is_marked)
            #     remove_marked_action(is_marked)
            #     await asyncio.sleep(1)
            #     color_log.log(f"Retry Get Aircon Status : {no} {cmd}", Color.Yellow, ColorLog.Level.INFO)
            #     _ = await self.async_send_and_get_result(0, no, cmd)    # type: ignore
            aircon_info: Aircon.Info | None = await self.async_send_and_get_result(0, aircon_no, aircon_cmd)
            if aircon_info:
                logger.info(f"Returned Get Aircon Status : {aircon_info.action} {aircon_info.opmode}) {aircon_info.cur_temp}")
                if aircon_info.opmode == PAYLOAD_AUTO:
                    aircon_info.action = PAYLOAD_ON
                if aircon_info.fanmode == PAYLOAD_SILENT:
                    aircon_info.fanmode = PAYLOAD_LOW
                return aircon_info
        return None

    async def aircon_tcp_send_handler_async(self, room: str, payload: str) -> Aircon.Info | None:
        aircon_no: int = int(self.get_room_aircon_number(room))
        aircon_cmd = Aircon.Info(PAYLOAD_STATUS, '', '', '', AIRCON_DEFAULT_TEMP, AIRCON_DEFAULT_TEMP)
        # {"mode": "off", "swing_mode": "off", "fan_mode": "low", "current_temp": "25.00", "target_temp": "26"}
        data_dict = json.loads(payload)
        logger.info(f"Aircorn = {room}, payload = {data_dict}")

        aircon_cmd.action = PAYLOAD_ON if data_dict[MQTT_MODE] != PAYLOAD_OFF else PAYLOAD_OFF
        aircon_cmd.opmode = data_dict[MQTT_MODE]
        aircon_cmd.cur_temp = float(data_dict.get(MQTT_CURRENT_TEMP, AIRCON_DEFAULT_TEMP))
        aircon_cmd.target_temp = int(float(data_dict.get(MQTT_TARGET_TEMP, AIRCON_DEFAULT_TEMP)))
        aircon_cmd.fanmove = data_dict[MQTT_SWING_MODE]
        aircon_cmd.fanmode = data_dict[MQTT_FAN_MODE]
        logger.info(f"no[{aircon_no}] ={aircon_cmd.action}, {aircon_cmd.opmode}")

        # Check if there's a marked file from a previous incomplete operation
        is_marked = check_marked_action(MARK_FILE_PREFIX)
        if is_marked:
            logger.info(f"Found marked file, attempting retry: {is_marked}")
            try:
                marked_path = is_marked if os.path.isabs(is_marked) else os.path.join('/tmp', is_marked)
                no, cmd_dict = read_last_action(marked_path)

                if not isinstance(no, int) or cmd_dict is None:
                    logger.warning(f"Invalid or corrupt marked action data, discarding")
                    remove_marked_action(marked_path)
                    return None

                # Reconstruct Aircon.Info from stored dict
                cmd = Aircon.Info(
                    cmd_dict.get('action', ''),
                    cmd_dict.get('opmode', ''),
                    cmd_dict.get('fanmove', ''),
                    cmd_dict.get('fanmode', ''),
                    cmd_dict.get('cur_temp', AIRCON_DEFAULT_TEMP),
                    cmd_dict.get('target_temp', AIRCON_DEFAULT_TEMP)
                )
                cmd.retry_count = cmd_dict.get('retry_count', 0)
                cmd.timestamp = cmd_dict.get('timestamp', time.time())

                # Check retry count and timestamp
                retry_count = cmd.retry_count
                timestamp = cmd.timestamp
                
                # Check if mark has expired (5 minutes)
                if time.time() - timestamp > MARK_EXPIRY_SECONDS:
                    logger.warning(f"Marked action expired (>{MARK_EXPIRY_SECONDS}s old), discarding")
                    remove_marked_action(marked_path)
                    return None
                
                # Check retry limit
                if retry_count >= MAX_MARKED_RETRY:
                    logger.error(f"Max retry attempts ({MAX_MARKED_RETRY}) reached for marked action, giving up")
                    remove_marked_action(marked_path)
                    return None

                # Increment retry count
                cmd.retry_count = retry_count + 1
                cmd.timestamp = timestamp  # Preserve original timestamp
                
                # For retry, use the stored command's temp values
                cmd.cur_temp = aircon_cmd.cur_temp
                cmd.target_temp = aircon_cmd.target_temp
                
                # Save updated retry count before attempting
                remove_marked_action(marked_path)
                marked_file = mark_last_action(MARK_FILE_PREFIX, no, cmd)
                
                aircon_info: Aircon.Info | None = await self.async_send_and_get_result(0, no, cmd)
                if aircon_info:
                    # Success - remove mark
                    remove_marked_action(marked_file)
                    if aircon_info.opmode == PAYLOAD_AUTO:
                        aircon_info.action = PAYLOAD_ON
                    if aircon_info.fanmode == PAYLOAD_SILENT:
                        aircon_info.fanmode = PAYLOAD_LOW
                    return aircon_info
                # If failed, mark is already saved with incremented retry_count
                return None
            except Exception as e:
                logger.error(f"Error during retry: {e}")
                # Don't remove mark on exception, let it retry next time
                return None

        # Initialize retry tracking for new mark
        aircon_cmd.retry_count = 0
        aircon_cmd.timestamp = time.time()
        marked_file = mark_last_action(MARK_FILE_PREFIX, aircon_no, aircon_cmd)
        aircon_info = None
        if self.check_aircon_communicationable_or_reset():
            aircon_info = await self.async_send_and_get_result(0, aircon_no, aircon_cmd)
            remove_marked_action(marked_file)
            if aircon_info:
                if aircon_info.opmode == PAYLOAD_AUTO:
                    aircon_info.action = PAYLOAD_ON
                if aircon_info.fanmode == PAYLOAD_SILENT:
                    aircon_info.fanmode = PAYLOAD_LOW
        return aircon_info

    # Sync wrapper for backward compatibility
    def aircon_tcp_send_handler(self, room: str, payload: str) -> Aircon.Info | None:
        # Get the current event loop or create a new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.aircon_tcp_send_handler_async(room, payload))

    async def async_scan_aircon_status(self, device_obj: Aircon):
        room_no_str = self.get_room_aircon_number(device_obj.room_name)
        no = int(room_no_str)
        logger.info(f"Aircorn Room name = {device_obj.room_name}, Number = {no}")

        aircon_info: Aircon.Info | None  = await self.async_get_current_status(no)
        if aircon_info:
            if self.notify_as_mqtt_aircon is not None:
                self.notify_as_mqtt_aircon(device_obj.name, device_obj.room_name, aircon_info)

    async def async_scan_aircons(self, now: float):
        for aircon in self.aircon:
            assert isinstance(aircon, Aircon)
            if (now - aircon.scan.tick) > cfg.WALLPAD_SCAN_INTERVAL_TIME:
                aircon.scan.tick = now
                logger.info(f">>>>>Rescan {aircon} Check Sending!!!!")
                await self.async_scan_aircon_status(aircon)
                await asyncio.sleep(cfg.PACKET_RESEND_INTERVAL_SEC)

    async def async_lgac_main_write_loop(self) -> None:
        while True:
            await asyncio.sleep(0.01)
            # if not self.command_queue.empty():
            #     (aircon_no, room_str, aircon_cmd) = self.command_queue.get()
            #     assert isinstance(aircon_cmd, Aircon.Info)
            #     aircon_info = await self.async_set_current_mode(aircon_no, aircon_cmd)
            #     if aircon_info:
            #         self.notify_to_homeassistant(DEVICE_AIRCON, room_str, aircon_info)

    async def async_scan_aircons_loop(self):
        while True:
            try:
                await self.async_scan_aircons(time.monotonic())
                await asyncio.sleep(0.01)
            except RuntimeError as e:
                logger.warning(f"LGAC communication error: {e} - will retry after reconnection delay")
                # Wait before retrying to avoid rapid reconnection attempts
                await asyncio.sleep(5.0)
            except Exception as e:
                logger.error(f"Unexpected error in LGAC scan loop: {e}")
                await asyncio.sleep(5.0)

import json
from enum import Enum
from struct import calcsize, pack, unpack

import config as cfg
from loguru import logger
from common.utils import is_partial_debug
from config import (KOCOM_LIGHT_SIZE, KOCOM_PLUG_SIZE, KOCOM_ROOM,
                    KOCOM_ROOM_THERMOSTAT)
from consts import (DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS, DEVICE_LIGHT,
                    DEVICE_PLUG, DEVICE_THERMOSTAT, MQTT_CURRENT_TEMP,
                    MQTT_MODE, MQTT_PRESET_MODE, MQTT_TARGET_TEMP,
                    PAYLOAD_FAN_ONLY, PAYLOAD_HEAT, PAYLOAD_HIGH, PAYLOAD_LOW,
                    PAYLOAD_MEDIUM, PAYLOAD_OFF, PAYLOAD_ON, Command,
                    DeviceType, FanSpeed, HeatMode, PacketType, State,
                    SwitchState)


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

        def calc_checksum(self, body: bytes | bytes):
            checksum = sum(body)
            return checksum & 0xff

        def match_data(self, data) -> bool:
            try:
                if len(data) != self._body_size:
                    logger.debug(f"Error: Kocom Packet size mismatch {len(data)} != {self._body_size}")
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
                logger.debug(f"Error: unpack data = [{e}]")
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
                logger.debug(f"Error: unpack data = [{e}]")
                return b''
            return all_body

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

    @classmethod
    def parse_kocom_device(cls, dev_hex: int) -> DeviceType | None:
        ret_enum = cls.KOCOM_DEVICE.get(dev_hex)
        return ret_enum if ret_enum is not None else None

    @classmethod
    def parse_kocom_command(cls, cmd_hex: int) -> Command | None:
        ret_enum = cls.KOCOM_COMMAND.get(cmd_hex)
        return ret_enum if ret_enum is not None else None

    # @classmethod
    def parse_kocom_room(self, strnum: str) -> str:
        ret_str = KOCOM_ROOM.get(strnum)
        return ret_str if ret_str is not None else ''

    # @classmethod
    def parse_kocom_room_thermo(self, strnum: str) -> str:
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
        KOCOM_ROOM_REV             = {v: k for k, v in KOCOM_ROOM.items()}
        ret_str = KOCOM_ROOM_REV.get(instr)
        return ret_str if ret_str is not None else ''

    def get_kocom_room_thermo_data(self, instr: str) -> str:
        KOCOM_ROOM_THERMOSTAT_REV  = {v: k for k, v in KOCOM_ROOM_THERMOSTAT.items()}
        ret_str = KOCOM_ROOM_THERMOSTAT_REV.get(instr)
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

        logger.debug(f"{dest_device_id}, {src_device_id}, {command}")

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


class ElevatorHandler(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()

    class ElevatorInput:
        def __init__(self) -> None:
            self.status = PAYLOAD_OFF
            self.room_str: str = ''

        def make_dict_data(self) -> dict:
            return {DEVICE_ELEVATOR: self.status}

    def parse_rs485_packet(self, value_p: bytes, room_no: int) -> dict:
        elevator = self.ElevatorInput()
        logger.debug(f"[Elevator] Data({value_p.hex()})")
        return elevator.make_dict_data()

    def handle_mqtt_tcp(self, payload: str, command: Command) -> bytes:
        import json
        data_dict = json.loads(payload)
        logger.debug(f"[Elevator] Data({data_dict})")

        new_packet = Device.PacketStruct()

        if command != Command.CHECK:
            make_ok = self.make_device_basic_info(new_packet, DeviceType.WALLPAD, DeviceType.ELEVATOR, Command.ON)
        else:
            make_ok = self.make_device_basic_info(new_packet, DeviceType.ELEVATOR, DeviceType.WALLPAD, Command.CHECK)

        if not make_ok:
            logger.warning(f"Error in make {DeviceType.ELEVATOR} packet!")

        packet = new_packet.get_full_bytes_packet()
        return packet


class FanHandler(Device):
    KOCOM_FAN_SPEED = {
        0x40: FanSpeed.LOW,
        0x80: FanSpeed.MEDIUM,
        0xc0: FanSpeed.HIGH,
        0x00: FanSpeed.OFF
    }

    KOCOM_FAN_SPEED_REV        = {v: k for k, v in KOCOM_FAN_SPEED.items()}

    def get_kocom_fan_speed_data(self, id: FanSpeed) -> int:
        ret_int = self.KOCOM_FAN_SPEED_REV.get(id)
        return ret_int if ret_int is not None else 0

    def parse_kocom_fan_speed(self, inbyte: int) -> FanSpeed | None:
        ret_enum = self.KOCOM_FAN_SPEED.get(inbyte)
        return ret_enum if ret_enum is not None else None

    class FanInput:
        def __init__(self) -> None:
            self.mode: State | None         = None
            self.fan_mode: FanSpeed | None  = None
            self.room_str: str              = ''

        def make_dict_data(self) -> dict:
            speed_string = PAYLOAD_LOW if self.fan_mode == FanSpeed.LOW else \
                PAYLOAD_MEDIUM if self.fan_mode == FanSpeed.MEDIUM else \
                PAYLOAD_HIGH if self.fan_mode == FanSpeed.HIGH else PAYLOAD_OFF

            fan = {
                MQTT_PRESET_MODE: speed_string
                # MQTT_STATE: speed_string,
                # 'percentage': percentage
            }
            return fan

    def __init__(self, room_name: str = '') -> None:
        super().__init__()

    def parse_rs485_packet(self, value_p: bytes, room_no: int) -> dict:
        fan = self.FanInput()
        fan.mode = State.ON if value_p[0] == 0x11 else State.OFF
        fan.fan_mode = self.parse_kocom_fan_speed(value_p[2] & 0xf0)
        return fan.make_dict_data()

    def parse_sensor(self, value_p: bytes) -> dict:
        co2_value = int(round(int(value_p[4]) * 100 + int(value_p[5])) / 10. * 10)
        sensor_ret = {
            "co2": co2_value
        }
        if is_partial_debug():
            logger.debug(f"[Packet input - Fan] = {value_p.hex()}, co2 = {co2_value}")

        return sensor_ret

    def handle_mqtt_tcp(self, payload: str, cmd_str: str, command: Command) -> bytes:
        import json
        data_dict = json.loads(payload)
        logger.debug(f"[Fan] Data({data_dict})")

        new_packet = Device.PacketStruct()

        if command == Command.CHECK:
            changed_cmd = Command.CHECK
        else:
            changed_cmd = Command.STATUS

        if changed_cmd != Command.CHECK:
            make_ok = self.make_device_basic_info(new_packet, DeviceType.FAN, DeviceType.WALLPAD, Command.STATUS)
            # make_ok = self.make_device_basic_info(new_packet, DeviceType.WALLPAD, self.device, Command.STATUS)
        else:
            make_ok = self.make_device_basic_info(new_packet, DeviceType.FAN, DeviceType.WALLPAD, Command.CHECK)

        if not make_ok:
            logger.warning(f"Error in make {DeviceType.FAN} packet!")

        if command != Command.CHECK:
            try:
                on_mode = True if data_dict[MQTT_PRESET_MODE] != PAYLOAD_OFF else False
                fan_mode = FanSpeed(data_dict[MQTT_PRESET_MODE])

                if on_mode:
                    new_packet.value_array = 0x1101000000000000
                else:
                    new_packet.value_array = 0x0001000000000000

                speed_byte_value = self.get_kocom_fan_speed_data(fan_mode)
                fanspeed_nibble = (0xf0 & speed_byte_value) << (5 * 8)
                new_packet.value_array |= fanspeed_nibble

                logger.debug(f"mode={on_mode}, {fan_mode}[{speed_byte_value:02x}]")
                logger.debug(f"value array = [{new_packet.value_array:016X}]")
            except Exception as e:
                logger.debug(f"[Make Packet] Error({e}) on Fan make_rs485_packet")

        packet = new_packet.get_full_bytes_packet()
        return packet


class GasHandler(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.state: State   = State.ON

    class GasInput:
        def __init__(self) -> None:
            self.command: str | None    = None
            self.room_str: str          = ''

        def make_dict_data(self) -> dict:
            return {DEVICE_GAS: self.command}

    def parse_rs485_packet(self, value_p: bytes, room_no: int) -> dict:
        gas = self.GasInput()
        gas.command = PAYLOAD_ON if self.state == State.ON else PAYLOAD_OFF
        return gas.make_dict_data()

    def handle_mqtt_tcp(self, payload: str, command: Command) -> bytes:
        import json
        data_dict = json.loads(payload)
        logger.debug(f"[Gas] Data({data_dict})")

        new_packet = Device.PacketStruct()

        modified_cmd = Command.OFF if command != Command.CHECK else command
        if not self.make_device_basic_info(new_packet, DeviceType.GAS, DeviceType.WALLPAD, modified_cmd):
            logger.warning(f"Error in make {DeviceType.GAS} packet!")

        packet = new_packet.get_full_bytes_packet()
        return packet


class LightHandler(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.room_name: str                 = room_name
        self.light_list: list[SwitchState]  = []

    def handle_mqtt_tcp(self, payload: str, room_str: str, command: Command) -> bytes:
        import json
        data_dict = json.loads(payload)
        logger.debug(f"[Light] Data({data_dict})")

        new_packet = Device.PacketStruct()

        if not self.make_device_basic_info(new_packet, DeviceType.LIGHT, DeviceType.WALLPAD, command, self.room_name):
            logger.warning(f"Error in make {DeviceType.LIGHT} packet!")

        try:
            new_packet.value_array = 0
            for light_name, stat in data_dict.items():
                light_num = int(light_name.lstrip(DEVICE_LIGHT))
                if light_num == 0:      # 0 is special meaning for all light
                    continue
                if stat == PAYLOAD_ON:
                    pad = 0xff
                    pad = pad << (8 - light_num) * 8
                    new_packet.value_array |= pad
            logger.debug(f"Lights Set Data = [{new_packet.value_array:016x}]")
        except Exception as e:
            logger.info(f"[Make Packet] Error({e}) on DeviceType.LIGHT")

        packet = new_packet.get_full_bytes_packet()
        return packet

    def parse_rs485_packet(self, value_p: bytes, room_no: int) -> dict:
        on_count = 0

        counts = 0
        switch = SwitchInput()
        device_name = DEVICE_LIGHT
        room_name = self.parse_kocom_room(f'{room_no:02d}')
        counts = self.parse_kocom_light_size(room_name)

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


class PlugHandler(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.room_name: str                 = room_name
        self.plug_list: list[SwitchState]   = []

    def handle_mqtt_tcp(self, payload: str, room_str: str, command: Command) -> bytes:
        import json
        data_dict = json.loads(payload)
        logger.debug(f"[Plug] Data({data_dict})")

        new_packet = Device.PacketStruct()

        if not self.make_device_basic_info(new_packet, DeviceType.PLUG, DeviceType.WALLPAD, command, self.room_name):
            logger.warning(f"Error in make {DeviceType.PLUG} packet!")

        try:
            new_packet.value_array = 0
            for light_name, stat in data_dict.items():
                light_num = int(light_name.lstrip(DEVICE_PLUG))
                if light_num == 0:      # 0 is special meaning for all light
                    continue
                if stat == PAYLOAD_ON:
                    pad = 0xff
                    pad = pad << (8 - light_num) * 8
                    new_packet.value_array |= pad
            logger.debug(f"Lights Set Data = [{new_packet.value_array:016x}]")
        except Exception as e:
            logger.info(f"[Make Packet] Error({e}) on DeviceType.LIGHT")

        packet = new_packet.get_full_bytes_packet()
        return packet

    def parse_rs485_packet(self, value_p: bytes, room_no: int) -> dict:
        on_count = 0

        counts = 0
        switch = SwitchInput()
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


class ThermostatHandler(Device):
    class ThermostatInput:
        def __init__(self) -> None:
            self.mode: HeatMode | None  = None
            self.current_temp           = 0
            self.target_temp            = 0
            self.room_str: str          = ''

        def make_dict_data(self) -> dict:
            mode_string = PAYLOAD_FAN_ONLY if self.mode == HeatMode.FAN_ONLY else \
                PAYLOAD_HEAT if self.mode == HeatMode.HEAT else PAYLOAD_OFF

            thermo = {
                MQTT_MODE: mode_string,
                MQTT_CURRENT_TEMP: self.current_temp,
                MQTT_TARGET_TEMP: self.target_temp
            }
            return thermo

    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.room_name: str     = room_name
        self.mode: HeatMode     = HeatMode.OFF
        self.current_temp: int  = cfg.INIT_TEMP
        self.target_temp: int   = cfg.INIT_TEMP

    def handle_mqtt_tcp(self, payload: str, room_str: str, command: Command) -> bytes:
        data_dict = json.loads(payload)
        logger.debug(f"[Thermostat] Data({data_dict})")

        new_packet = Device.PacketStruct()

        if not self.make_device_basic_info(new_packet, DeviceType.THERMOSTAT, DeviceType.WALLPAD, command, self.room_name):
            logger.warning(f"Error in make {DeviceType.THERMOSTAT} packet!")

        try:
            if data_dict[MQTT_MODE] == PAYLOAD_HEAT:
                new_packet.value_array = 0x1100000000000000
            elif data_dict[MQTT_MODE] == PAYLOAD_OFF:
                new_packet.value_array = 0x0001000000000000
            else:
                new_packet.value_array = 0x1101000000000000
            new_packet.value_array |= (0xff & int(float(data_dict[MQTT_TARGET_TEMP]))) << (5 * 8)
        except Exception as e:
            logger.debug(f"[Make Packet] Error({e}) on DeviceType.THERMOSTAT")

        packet = new_packet.get_full_bytes_packet()
        return packet

    def parse_rs485_packet(self, value_p: bytes, room_no: int) -> dict:
        thermo = self.ThermostatInput()

        if value_p[0] == 0x11:
            is_heat_mode = True
        else:
            is_heat_mode = False

        if value_p[1] == 0x01:
            is_away_mode = True
        else:
            is_away_mode = False

        thermo.current_temp = int(value_p[4])
        if is_heat_mode and is_away_mode:
            thermo.mode = HeatMode.FAN_ONLY
            thermo.target_temp = cfg.INIT_TEMP
        elif is_heat_mode:
            thermo.mode = HeatMode.HEAT
            thermo.target_temp = int(value_p[2])
        else:
            thermo.mode = HeatMode.OFF
            thermo.target_temp = cfg.INIT_TEMP
        return thermo.make_dict_data()


class RS485DeviceHandler:
    def __init__(self, source_device: DeviceType | None,
                 dest_device: DeviceType | None,
                 packet_type: PacketType | None, 
                 source_room_no: int) -> None:
        self.src_dev = source_device
        self.dest_dev = dest_device
        self.packet_type = packet_type
        self.room_no = source_room_no

    def parse_packet(self, packet) -> dict:
        result = {}

        if self.src_dev == DeviceType.FAN:
            dev = FanHandler()
        elif self.src_dev == DeviceType.LIGHT:
            dev = LightHandler()
        elif self.src_dev == DeviceType.PLUG:
            dev = PlugHandler()
        elif self.src_dev == DeviceType.THERMOSTAT:
            dev = ThermostatHandler()
        elif self.src_dev == DeviceType.GAS:
            dev = GasHandler()
        elif self.src_dev == DeviceType.WALLPAD and self.dest_dev == DeviceType.ELEVATOR:
            dev = ElevatorHandler()
        else:
            logger.debug(f"MUST NOT BE HERE!! or just Elevator "
                f"({packet.hex()}, {self.src_dev}, {self.dest_dev}, {self.packet_type})")
            return result

        if self.src_dev != self.dest_dev:
            result = dev.parse_rs485_packet(packet, self.room_no)
        else:
            if type(dev) is FanHandler:
                temp_dict = dev.parse_sensor(packet)
                logger.info(f"In Fan {packet.hex()} = {temp_dict}")
                if type(temp_dict) is dict and temp_dict['co2'] != 0:
                    result = temp_dict
        return result

    def make_packet(self, device_str: str, payload: str, command: Command, room_str) -> bytes:
        packet: bytes = b''

        logger.debug(f"tcp_send_handler : {device_str},{command} = {payload}")
        if device_str == DEVICE_GAS:
            gas = GasHandler()
            packet: bytes = gas.handle_mqtt_tcp(payload, command)
        elif device_str == DEVICE_ELEVATOR:
            elevator = ElevatorHandler()
            packet: bytes = elevator.handle_mqtt_tcp(payload, command)
        elif device_str == DEVICE_LIGHT:
            light = LightHandler(room_str)
            packet: bytes = light.handle_mqtt_tcp(payload, room_str, command)
        elif device_str == DEVICE_PLUG:
            plug = PlugHandler(room_str)
            packet: bytes = plug.handle_mqtt_tcp(payload, room_str, command)
        elif device_str == DEVICE_THERMOSTAT:
            device_str = DEVICE_THERMOSTAT
            thermostat = ThermostatHandler(room_str)
            packet: bytes = thermostat.handle_mqtt_tcp(payload, room_str, command)
        elif device_str == DEVICE_FAN:
            device_str = DEVICE_FAN
            fan = FanHandler()
            packet: bytes = fan.handle_mqtt_tcp(payload, f'{MQTT_PRESET_MODE}_set', command)
        else:
            packet: bytes = b''

        return packet

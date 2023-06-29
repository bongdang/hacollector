from __future__ import annotations

import config as cfg
from classes.basicdevice import Device
from classes.utils import Color, ColorLog
from consts import (DEVICE_THERMOSTAT, MQTT_CURRENT_TEMP, MQTT_MODE,
                    MQTT_TARGET_TEMP, PAYLOAD_FAN_ONLY, PAYLOAD_HEAT,
                    PAYLOAD_OFF, Command, DeviceType, HeatMode)


class Thermostat(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.device             = DeviceType.THERMOSTAT
        self.name: str          = DEVICE_THERMOSTAT
        self.room_name: str     = room_name
        self.mode: HeatMode     = HeatMode.OFF
        self.current_temp: int  = cfg.INIT_TEMP
        self.target_temp: int   = cfg.INIT_TEMP
        self.scan.reset()

    def make_rs485_packet(self, cmd: Command) -> bytes:
        new_packet = Device.PacketStruct()
        color_log = ColorLog()

        if not self.make_device_basic_info(new_packet, self.device, DeviceType.WALLPAD, cmd, self.room_name):
            color_log.log(f"Error in make {self.device} packet!", Color.Red, ColorLog.Level.WARN)

        if cmd != Command.CHECK:
            try:
                if self.mode == HeatMode.HEAT:
                    new_packet.value_array = 0x1100000000000000
                elif self.mode == HeatMode.OFF:
                    new_packet.value_array = 0x0001000000000000
                else:
                    new_packet.value_array = 0x1101000000000000
                new_packet.value_array |= (0xff & int(float(self.target_temp))) << (5 * 8)
            except Exception as e:
                color_log.log(f"[Make Packet] Error({e}) on DeviceType.THERMOSTAT", Color.White, ColorLog.Level.DEBUG)

        packet = new_packet.get_full_bytes_packet()
        color_log.log(f"[Packet made - thermostat] = {packet.hex()}", Color.White, ColorLog.Level.DEBUG)
        return packet

    def handle_mqtt(self, payload: str, cmd_str: str) -> None:
        color_log = ColorLog()
        color_log.log(
            f"from MQTT(THERMOSTAT) : cmd_str={cmd_str}, payload={payload}",
            Color.White,
            ColorLog.Level.DEBUG
        )
        if cmd_str != MQTT_MODE:
            self.target_temp = int(float(payload))
            self.mode = HeatMode.HEAT
        elif cmd_str == MQTT_MODE:
            self.mode = HeatMode(payload)

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

    def parse(self, value_p: bytes, room_no: int) -> dict:
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

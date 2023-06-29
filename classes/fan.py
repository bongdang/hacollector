from __future__ import annotations

import config as cfg
from classes.basicdevice import Device
from classes.utils import Color, ColorLog
from consts import (DEVICE_FAN, MQTT_FAN_MODE, MQTT_FAN_SPEED, PAYLOAD_HIGH,
                    PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_OFF, PAYLOAD_ON,
                    Command, DeviceType, FanSpeed, State)


class Fan(Device):
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

    def __init__(self) -> None:
        super().__init__()
        self.device             = DeviceType.FAN
        self.name               = DEVICE_FAN
        self.mode: State        = State.OFF
        self.fan_mode: FanSpeed = FanSpeed.OFF
        self.scan.reset()

    def make_rs485_packet(self, cmd: Command) -> bytes:
        new_packet = Device.PacketStruct()
        color_log = ColorLog()

        if not self.make_device_basic_info(new_packet, self.device, DeviceType.WALLPAD, cmd):
            color_log.log(f"Error in make {self.device} packet!", Color.Red, ColorLog.Level.WARN)

        if cmd != Command.CHECK:
            try:
                color_log.log(f"mode={self.mode}, fan_mode={self.fan_mode}", Color.Yellow, ColorLog.Level.DEBUG)
                if self.fan_mode == PAYLOAD_LOW:
                    fan_mode = FanSpeed.LOW
                elif self.fan_mode == PAYLOAD_MEDIUM:
                    fan_mode = FanSpeed.MEDIUM
                elif self.fan_mode == PAYLOAD_HIGH:
                    fan_mode = FanSpeed.HIGH
                else:
                    fan_mode = FanSpeed.OFF

                if self.mode == PAYLOAD_ON:
                    new_packet.value_array = 0x1100000000000000
                elif self.mode == PAYLOAD_OFF:
                    new_packet.value_array = 0x0001000000000000

                fanspeed_nibble = (0xf0 & self.get_kocom_fan_speed_data(fan_mode)) << (5 * 8)
                new_packet.value_array |= fanspeed_nibble
            except Exception as e:
                color_log.log(f"[Make Packet] Error({e}) on Fan make_rs485_packet", Color.Red, ColorLog.Level.DEBUG)

        packet = new_packet.get_full_bytes_packet()

        color_log.log(f"[Packet made - Fan] = {packet.hex()}", Color.Yellow, ColorLog.Level.DEBUG)
        return packet

    def handle_mqtt(self, payload: str, cmd_str: str) -> None:
        if cmd_str == MQTT_FAN_MODE:
            self.fan_mode = FanSpeed(cfg.DEFAULT_SPEED)
            self.mode = State(payload)
        elif cmd_str == MQTT_FAN_SPEED:
            self.fan_mode = FanSpeed(cfg.DEFAULT_SPEED) if payload == PAYLOAD_ON else FanSpeed(PAYLOAD_OFF)
            self.mode = State.ON

    class FanInput:
        def __init__(self) -> None:
            self.mode: State | None         = None
            self.fan_mode: FanSpeed | None  = None
            self.room_str: str              = ''

        def make_dict_data(self) -> dict:
            mode_string = PAYLOAD_ON if self.mode == State.ON else PAYLOAD_OFF
            speed_string = PAYLOAD_LOW if self.fan_mode == FanSpeed.LOW else \
                PAYLOAD_MEDIUM if self.fan_mode == FanSpeed.MEDIUM else \
                PAYLOAD_HIGH if self.fan_mode == FanSpeed.HIGH else PAYLOAD_OFF
            if speed_string == PAYLOAD_OFF:
                mode_string = PAYLOAD_OFF
            fan = {
                MQTT_FAN_MODE: mode_string,
                MQTT_FAN_SPEED: speed_string
            }
            return fan

    def parse(self, value_p: bytes, room_no: int) -> dict:
        fan = self.FanInput()
        fan.mode = State.ON if value_p[0] == 0x11 else State.OFF
        fan.fan_mode = self.parse_kocom_fan_speed(value_p[2] & 0xf0)
        return fan.make_dict_data()

    def parse_sensor(self, value_p: bytes, room_no: int) -> dict:
        co2_value = int(value_p[4]) * 100 + int(value_p[5])
        sensor_ret = {
            "co2": co2_value
        }
        color_log = ColorLog()
        if color_log.partial_debug:
            color_log.log(
                f"[Packet input - Fan] = {value_p.hex()}, co2 = {co2_value}",
                Color.Yellow,
                ColorLog.Level.WARN
            )

        return sensor_ret

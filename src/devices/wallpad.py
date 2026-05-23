from __future__ import annotations

from typing import Callable, NamedTuple

import config as cfg
from loguru import logger
from config import KOCOM_LIGHT_SIZE, KOCOM_PLUG_SIZE
from consts import (DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS,
                    DEVICE_LIGHT, DEVICE_PLUG, DEVICE_THERMOSTAT,
                    DEVICE_WALLPAD, Command, DeviceType, DeviceTypeMatch)
from devices.basedevice import Device
from devices.elevator import Elevator
from devices.fan import Fan
from devices.gas import Gas
from devices.light import Light
from devices.plug import Plug
from devices.thermostat import Thermostat


class EnabledDevice(NamedTuple):
    type: DeviceType
    devicelist: list[Device]


class WallPad:
    def __init__(self) -> None:
        self.elevator: list[Device]                     = []
        self.gas: list[Device]                          = []
        self.thermostat: list[Device]                   = []
        self.light: list[Device]                        = []
        self.plug: list[Device]                         = []
        self.fan: list[Device]                          = []
        self.device_list: list[Device]                  = []
        self.enabled_device_list: list[EnabledDevice]   = []

    def set_notify_to_homeassistant(self, send_state_to_homeassistant):
        self.notify_to_homeassistant: Callable[[str, str, dict], None] = send_state_to_homeassistant

    def set_send_mqtt2tcp_command(self, send_mqtt2tcp_command):
        self.send_mqtt2tcp_command: Callable[[str, str, str, Command], None] = send_mqtt2tcp_command

    def prepare_enabled(self, enabled: list):
        self.set_initial_state(enabled)

    def set_initial_state(self, enabled: list) -> None:
        check_list = [DeviceType.WALLPAD,
                      DeviceType.LIGHT,
                      DeviceType.THERMOSTAT,
                      DeviceType.PLUG,
                      DeviceType.ELEVATOR,
                      DeviceType.GAS,
                      DeviceType.FAN]
        check_list.append(DeviceType.AIRCON)
        for d_name in check_list:
            if d_name in enabled:
                logger.debug(f'dev = {d_name}')
                if d_name == DeviceType.ELEVATOR:
                    self.elevator = []
                    elevator = Elevator()
                    self.elevator.append(elevator)
                    self.device_list.append(elevator)
                    self.enabled_device_list.append(EnabledDevice(d_name, self.elevator))
                elif d_name == DeviceType.GAS:
                    self.gas = []
                    gas = Gas()
                    self.gas.append(gas)
                    self.device_list.append(gas)
                    self.enabled_device_list.append(EnabledDevice(d_name, self.gas))
                elif d_name == DeviceType.FAN:
                    self.fan = []
                    fan = Fan()
                    self.fan.append(fan)
                    self.device_list.append(fan)
                    self.enabled_device_list.append(EnabledDevice(d_name, self.fan))
                elif d_name == DeviceType.THERMOSTAT:
                    self.thermostat = []
                    for r_name in cfg.KOCOM_ROOM_THERMOSTAT.values():
                        thermostat = Thermostat(r_name)
                        self.thermostat.append(thermostat)
                        self.device_list.append(thermostat)
                    self.enabled_device_list.append(EnabledDevice(d_name, self.thermostat))
                elif d_name == DeviceType.LIGHT:
                    self.light = []
                    for r_name in cfg.KOCOM_ROOM.values():
                        if r_name in KOCOM_LIGHT_SIZE:
                            light = Light(r_name)
                            light.set_initial_state(KOCOM_LIGHT_SIZE[r_name])
                            self.light.append(light)
                            self.device_list.append(light)
                    self.enabled_device_list.append(EnabledDevice(d_name, self.light))
                elif d_name == DeviceType.PLUG:
                    self.plug = []
                    for r_name in cfg.KOCOM_ROOM.values():
                        if r_name in KOCOM_PLUG_SIZE:
                            plug = Plug(r_name)
                            plug.set_initial_state(KOCOM_PLUG_SIZE[r_name])
                            self.plug.append(plug)
                            self.device_list.append(plug)
                    self.enabled_device_list.append(EnabledDevice(d_name, self.plug))

    def _get_single(self, device_list: list, name: str) -> Device:
        if device_list and len(device_list) == 1:
            return device_list[0]
        raise ValueError(f"get_{name} error!")

    def _get_by_room(self, device_list: list, room_name: str, name: str) -> Device:
        if device_list:
            for item in device_list:
                if item.room_name == room_name:
                    return item
        raise ValueError(f"get_{name} error! room={room_name}")

    def get_elevator(self) -> Elevator:
        return self._get_single(self.elevator, 'elevator')  # type: ignore[return-value]

    def get_gas(self) -> Gas:
        return self._get_single(self.gas, 'gas')  # type: ignore[return-value]

    def get_fan(self) -> Fan:
        return self._get_single(self.fan, 'fan')  # type: ignore[return-value]

    def get_thermostat(self, room_name: str) -> Thermostat:
        return self._get_by_room(self.thermostat, room_name, 'thermostat')  # type: ignore[return-value]

    def get_light(self, room_name: str) -> Light:
        return self._get_by_room(self.light, room_name, 'light')  # type: ignore[return-value]

    def get_plug(self, room_name: str) -> Plug:
        return self._get_by_room(self.plug, room_name, 'plug')  # type: ignore[return-value]

    def get_real_device_from_subdevice(self, subdevice: str) -> str:
        real_device: str = ''
        if DEVICE_LIGHT in subdevice:
            real_device = DEVICE_LIGHT
        elif DEVICE_PLUG in subdevice:
            real_device = DEVICE_PLUG
        elif DEVICE_ELEVATOR in subdevice:
            real_device = DEVICE_ELEVATOR
        elif DEVICE_GAS in subdevice:
            real_device = DEVICE_GAS
        elif DEVICE_THERMOSTAT in subdevice:
            real_device = DEVICE_THERMOSTAT
        elif DEVICE_FAN in subdevice:
            real_device = DEVICE_FAN
        return real_device

    def is_multi_info_topic(self, device: str) -> bool:
        if device in (cfg.HA_LIGHT, cfg.HA_SWITCH):
            return True
        else:
            return False

    def handle_kocom_mqtt_message(self, topic: list[str], payload):
        device_str = topic[1]
        cmd_str = topic[3]

        if self.is_multi_info_topic(device_str):
            room_and_device = topic[2].split('_')
            room_str = room_and_device[0]
            sub_device_str = room_and_device[1]
        else:
            room_str = topic[2]
            sub_device_str = ''

        self.handle_from_mqtt(device_str, sub_device_str, room_str, cmd_str, payload)

    def handle_from_mqtt(self, device_str: str, sub_device_str: str, room_str: str, cmd_str: str, payload: str) -> None:
        try:
            logger.debug(f"Handle HA CMD = {device_str},{sub_device_str},{room_str},{cmd_str},{payload}")
            if self.is_multi_info_topic(device_str):
                device_str = self.get_real_device_from_subdevice(sub_device_str)
                if device_str == '':
                    logger.debug(f"Parse Error! not matched sub device{sub_device_str}")
                    return

                if device_str == DEVICE_LIGHT:
                    light = self.get_light(room_str)
                    light.handle_mqtt(payload, sub_device_str, room_str)
                    self.send_mqtt2tcp_command(DEVICE_LIGHT, room_str, light.make_command_from_data(), Command.STATUS)
                elif device_str == DEVICE_PLUG:
                    plug = self.get_plug(room_str)
                    plug.handle_mqtt(payload, sub_device_str, room_str)
                    self.send_mqtt2tcp_command(DEVICE_PLUG, room_str, plug.make_command_from_data(), Command.STATUS)
                elif device_str == DEVICE_ELEVATOR:
                    elevator = self.get_elevator()
                    next = elevator.handle_mqtt(payload)
                    room_str = DEVICE_WALLPAD
                    if True and next:       # maybe always check status is enough
                        self.send_mqtt2tcp_command(DEVICE_ELEVATOR, 
                                                   room_str, elevator.make_command_from_data(), Command.ON)
                elif device_str == DEVICE_GAS:
                    gas = self.get_gas()
                    next = gas.handle_mqtt(payload)
                    if next:
                        self.send_mqtt2tcp_command(DEVICE_GAS, room_str, gas.make_command_from_data(), Command.STATUS)
                else:
                    pass

                logger.debug(f"[From HA]{device_str}/{room_str}/{sub_device_str}/{cmd_str} = {payload}")
            elif device_str == cfg.HA_CLIMATE:
                device_str = DEVICE_THERMOSTAT
                thermostat = self.get_thermostat(room_str)
                thermostat.handle_mqtt(payload, cmd_str)
                self.send_mqtt2tcp_command(DEVICE_THERMOSTAT, 
                                           room_str, thermostat.make_command_from_data(), Command.STATUS)
                logger.info(f"[From HA]{device_str}/{room_str}/set:"
                    f"[mode={thermostat.mode},target_temp={thermostat.target_temp}]")

            elif device_str == cfg.HA_FAN:
                device_str = DEVICE_FAN
                logger.info(f"cmd = {cmd_str}, payload = {payload}")
                fan = self.get_fan()
                fan.handle_mqtt(payload, cmd_str)
                room_str = DEVICE_WALLPAD
                self.send_mqtt2tcp_command(DEVICE_FAN, room_str, fan.make_command_from_data(), Command.STATUS)
                logger.info(f"[From HA]{device_str}/{room_str}/set = [mode={fan.mode}, fan_mode={fan.fan_mode}]")

        except Exception as e:
            logger.info(f"[From HA]Error [{e}] {device_str}/{room_str}/{cmd_str} = {payload}")

    def scan_wallpad_devices(self, now: float):
        try:
            for dev_type, device_list in self.enabled_device_list:
                # color_log.log(f'Scan Device list =[{device_list}]', Color.Cyan, ColorLog.Level.DEBUG)
                if type(device_list) is list:
                    if len(device_list) < 1:
                        break
                    for obj in device_list:
                        if isinstance(obj, Device):
                            device_str = DeviceTypeMatch.match_kocom_device(dev_type)
                            if (now - obj.scan.tick) > cfg.WALLPAD_SCAN_INTERVAL_TIME and not isinstance(obj, Elevator):
                                # elevator must exclude - from org source. why?
                                obj.scan.tick = now
                                logger.debug(f">>>>>{obj} Check append to Queue.")
                                room = "wallpad"
                                if dev_type == DeviceType.LIGHT:
                                    assert (isinstance(obj, Light))
                                    room = obj.room_name
                                elif dev_type == DeviceType.PLUG:
                                    assert (isinstance(obj, Plug))
                                    room = obj.room_name
                                elif dev_type == DeviceType.ELEVATOR:
                                    assert (isinstance(obj, Elevator))
                                elif dev_type == DeviceType.THERMOSTAT:
                                    assert (isinstance(obj, Thermostat))
                                    room = obj.room_name
                                elif dev_type == DeviceType.FAN:
                                    assert (isinstance(obj, Fan))
                                else:                                 # dev_type == DeviceType.GAS:
                                    assert (isinstance(obj, Gas))

                                self.send_mqtt2tcp_command(device_str,
                                                           room,
                                                           obj.make_command_from_data(),
                                                           Command.CHECK)
        except Exception as e:
            logger.info(f"Scan Walpad Error [{e}]")

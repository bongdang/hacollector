from __future__ import annotations

from queue import PriorityQueue
from typing import Callable, NamedTuple

import config as cfg
from classes.basicdevice import Device
from classes.elevator import Elevator
from classes.fan import Fan
from classes.gas import Gas
from classes.light import Light
from classes.plug import Plug
from classes.thermostat import Thermostat
from classes.utils import Color, ColorLog
from config import KOCOM_LIGHT_SIZE, KOCOM_PLUG_SIZE
from consts import (DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS,  # DEVICE_WALLPAD,
                    DEVICE_LIGHT, DEVICE_PLUG, DEVICE_THERMOSTAT,
                    PRIORITY_HIGH, PRIORITY_LOW, Command, DeviceType)


class EnabledDevice(NamedTuple):
    type: DeviceType
    devicelist: list[Device]


class WallPad:
    class QueueWraper:
        def __init__(self, obj: Device) -> None:
            self.device = obj

        def __lt__(self, other: Device) -> bool:
            return id(self.device) < id(other)

    def __init__(self) -> None:
        self.elevator: list[Device]                     = []
        self.gas: list[Device]                          = []
        self.thermostat: list[Device]                   = []
        self.light: list[Device]                        = []
        self.plug: list[Device]                         = []
        self.fan: list[Device]                          = []
        self.device_list: list[Device]                  = []
        self.enabled_device_list: list[EnabledDevice]   = []
        self.command_queue: PriorityQueue = PriorityQueue()

    def set_notify_function(self, send_state_to_homeassistant):
        self.notify_to_homeassistant: Callable[[str, str, dict], None] = send_state_to_homeassistant

    def prepare_enabled(self, enabled: list):
        self.set_initial_state(enabled)

    def set_initial_state(self, enabled: list) -> None:
        check_list = list(Device.KOCOM_DEVICE.values())
        check_list.append(DeviceType.AIRCON)
        color_log = ColorLog()
        for d_name in check_list:
            if d_name in enabled:
                color_log.log(f'dev = {d_name}', Color.Cyan, ColorLog.Level.DEBUG)
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
                            plug = Plug()
                            plug.set_initial_state(KOCOM_PLUG_SIZE[r_name])
                            self.plug.append(plug)
                            self.device_list.append(plug)
                    self.enabled_device_list.append(EnabledDevice(d_name, self.plug))

    def get_elevator(self) -> Elevator:
        if self.elevator is not None and len(self.elevator) == 1:
            elevator = self.elevator[0]
            assert isinstance(elevator, Elevator)
            return elevator
        assert False, "get_elevator error!"

    def get_gas(self) -> Gas:
        if self.gas is not None and len(self.gas) == 1:
            gas = self.gas[0]
            assert isinstance(gas, Gas)
            return gas
        assert False, "get_gas error!"

    def get_fan(self) -> Fan:
        if self.fan is not None and len(self.fan) == 1:
            fan = self.fan[0]
            assert isinstance(fan, Fan)
            return fan
        assert False, "get_fan error!"

    def get_thermostat(self, room_name) -> Thermostat:
        if self.thermostat is not None and len(self.thermostat) >= 1:
            for item in self.thermostat:
                assert isinstance(item, Thermostat)
                if item.room_name == room_name:
                    return item
        assert False, "get_thermostat error!"

    def get_light(self, room_name) -> Light:
        if self.light is not None and len(self.light) >= 1:
            for item in self.light:
                assert isinstance(item, Light)
                if item.room_name == room_name:
                    return item
        assert False, "get_light error!"

    def get_plug(self, room_name) -> Plug:
        if self.plug is not None and len(self.plug) == 1:
            for item in self.plug:
                assert isinstance(item, Plug)
                if item.room_name == room_name:
                    return item
        assert False, "get_plug error!"

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

    def handle_wallpad_mqtt_message(self, topic: list[str], payload):
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
        color_log = ColorLog()
        try:
            if self.is_multi_info_topic(device_str):
                device_str = self.get_real_device_from_subdevice(sub_device_str)
                if device_str == '':
                    color_log.log(
                        f"Parse Error! not matched sub device{sub_device_str}",
                        Color.Red,
                        ColorLog.Level.DEBUG
                    )
                    return

                if device_str == DEVICE_GAS:
                    gas = self.get_gas()
                    next = gas.handle_mqtt(payload)
                    if next:
                        self.command_queue.put((PRIORITY_HIGH, WallPad.QueueWraper(gas), Command.STATUS))
                elif device_str == DEVICE_ELEVATOR:
                    elevator = self.get_elevator()
                    next = elevator.handle_mqtt(payload)
                    if True and next:       # maybe always check status is enough
                        self.command_queue.put((PRIORITY_HIGH, WallPad.QueueWraper(elevator), Command.STATUS))
                    # else:
                    #     self.notify_to_homeassistant(device_str, DEVICE_WALLPAD, payload)
                elif device_str == DEVICE_LIGHT:
                    light = self.get_light(room_str)
                    light.handle_mqtt(payload, sub_device_str, room_str)
                    self.command_queue.put((PRIORITY_HIGH, WallPad.QueueWraper(light), Command.STATUS))
                elif device_str == DEVICE_PLUG:
                    plug = self.get_plug(room_str)
                    plug.handle_mqtt(payload, sub_device_str, room_str)
                    self.command_queue.put((PRIORITY_HIGH, WallPad.QueueWraper(plug), Command.STATUS))
                else:
                    pass

                color_log.log(f"[From HA]{device_str}/{room_str}/{sub_device_str}/{cmd_str} = {payload}")

            elif device_str == cfg.HA_CLIMATE:
                device_str = DEVICE_THERMOSTAT
                thermostat = self.get_thermostat(room_str)
                thermostat.handle_mqtt(payload, cmd_str)
                self.command_queue.put((PRIORITY_HIGH, WallPad.QueueWraper(thermostat), Command.STATUS))
                color_log.log(
                    f"[From HA]{device_str}/{room_str}/set:"
                    f"[mode={thermostat.mode},target_temp={thermostat.target_temp}]"
                )

            elif device_str == cfg.HA_FAN:
                device_str = DEVICE_FAN
                color_log.log(f"cmd = {cmd_str}, payload = {payload}")
                fan = self.get_fan()
                fan.handle_mqtt(payload, cmd_str)
                self.command_queue.put((PRIORITY_HIGH, WallPad.QueueWraper(fan), Command.STATUS))
                color_log.log(f"[From HA]{device_str}/{room_str}/set = [mode={fan.mode}, fan_mode={fan.fan_mode}]")

        except Exception as e:
            color_log.log(f"[From HA]Error [{e}] {device_str}/{room_str}/{cmd_str} = {payload}", Color.Red)

    def scan_wallpad_devices(self, now: float):
        color_log = ColorLog()
        try:
            for _, device_list in self.enabled_device_list:
                # color_log.log(f'Scan Device list =[{device_list}]', Color.Cyan, ColorLog.Level.DEBUG)
                if type(device_list) == list:
                    if len(device_list) < 1:
                        break
                    for obj in device_list:
                        if isinstance(obj, Device):
                            if (now - obj.scan.tick) > cfg.WALLPAD_SCAN_INTERVAL_TIME and not isinstance(obj, Elevator):
                                # elevator must exclude - from org source. why?
                                obj.scan.tick = now
                                color_log.log(f">>>>>{obj} Check append to Queue.", Color.Blue, ColorLog.Level.DEBUG)
                                self.command_queue.put((PRIORITY_LOW, WallPad.QueueWraper(obj), Command.CHECK))
        except Exception as e:
            color_log.log(f"Scan Walpad Error [{e}]")

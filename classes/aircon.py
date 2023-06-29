from __future__ import annotations

from classes.basicdevice import Device
from consts import DEVICE_AIRCON, DeviceType


class Aircon(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.device: DeviceType = DeviceType.AIRCON
        self.name: str          = DEVICE_AIRCON
        self.room_name: str     = room_name
        self.action: str        = ''
        self.fanmove: str       = ''
        self.fanmode: str      = ''
        self.current_temp: float  = 25
        self.target_temp: int   = 25

    def set_initial_state(self) -> None:
        self.scan.reset()

    class Info:
        def __init__(self, action, opmode, fanmode, fanspeed, cur_temp, target_temp) -> None:
            self.action: str        = action
            self.opmode: str        = opmode
            self.fanmove: str       = fanmode
            self.fanmode: str      = fanspeed
            self.cur_temp: float      = cur_temp
            self.target_temp: int   = target_temp

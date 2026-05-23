from consts import AIRCON_DEFAULT_TEMP, DEVICE_AIRCON, DeviceType
from devices.basedevice import Device


class Aircon(Device):
    def __init__(self, room_name: str = '') -> None:
        super().__init__()
        self.device: DeviceType = DeviceType.AIRCON
        self.name: str          = DEVICE_AIRCON
        self.room_name: str     = room_name
        self.action: str        = ''
        self.fanmove: str       = ''
        self.fanmode: str      = ''
        self.current_temp: float  = AIRCON_DEFAULT_TEMP
        self.target_temp: int   = AIRCON_DEFAULT_TEMP

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
            # Retry tracking for marked actions
            self.retry_count: int = 0
            self.timestamp: float = 0.0

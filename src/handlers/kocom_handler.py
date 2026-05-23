import json

# import config as cfg
from tcphandler.appconf_tcphandler import MainConfig
from loguru import logger
from consts import DeviceType
from devices.wallpad import WallPad


class KocomHandlerMqtt:
    def __init__(self, config: MainConfig) -> None:
        self.name           = config.kocom_devicename
        self.enabled_dev    = []
        self.wallpad        = WallPad()

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

    def kocom_tcp2mqtt_handler(self, device: str, command: str, room: str, payload: str) -> None:
        try:
            payload_value = json.loads(payload)
            assert isinstance(payload_value, dict)
            payload_value_str = payload_value
            self.wallpad.notify_to_homeassistant(device, room, payload_value_str)
            logger.debug(f"Yes. {device},{command},{room},{payload} sent to HA.")
        except Exception as e:
            logger.debug(f"Error [{e}]in handling packets [{payload}]")

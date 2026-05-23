import os
from configparser import ConfigParser

import config as cfg
from loguru import logger
from common.utils import set_partial_debug


class MainConfig:
    def __init__(self) -> None:
        self.device_list: dict[str, str]    = {}
        self.kocom_server: str              = ''
        self.kocom_port: str                = '0'
        self.kocom_devicename: str          = cfg.CONF_KOCOM_DEVICE_NAME
        self.aircon_server: str             = ''
        self.aircon_port: str               = '0'
        self.aircon_devicename: str         = cfg.CONF_AIRCON_DEVICE_NAME
        self.mqtt_anonymous: str            = ''
        self.mqtt_server: str               = ''
        self.mqtt_port: str                 = ''
        self.mqtt_id: str                   = ''
        self.mqtt_pw: str                   = ''
        self.log_level: str                 = cfg.CONF_LOGLEVEL

    @staticmethod
    def _clean_optional(value: str | None) -> str:
        return value.strip() if isinstance(value, str) else ''

    @staticmethod
    def _has_valid_port(value: str) -> bool:
        try:
            return int(value.strip()) > 0
        except (AttributeError, ValueError):
            return False

    def read_config_file(self, config: ConfigParser) -> bool:
        try:
            # first, check RS485 Device
            if cfg.CONF_RS485_DEVICES not in config:
                logger.warning(f"Configuration file missing [{cfg.CONF_RS485_DEVICES}] section.")
                return False
            rs485_devices = config[cfg.CONF_RS485_DEVICES]
            if rs485_devices is not None and len(rs485_devices) >= 1:
                kocom_section = None
                aircon_section = None
                for top_device in rs485_devices:
                    logger.debug(f"device section = {top_device}")
                    if top_device == cfg.CONF_KOCOM_DEVICE_NAME.lower():
                        kocom_section = rs485_devices[top_device]
                    if top_device == cfg.CONF_AIRCON_DEVICE_NAME.lower():
                        aircon_section = rs485_devices[top_device]
                logger.debug(f"aircon section is {aircon_section}")
                if kocom_section is None and aircon_section is None:
                    logger.critical("kocom or aircon section must be exist.")
                    return False
                # KOCOM Device Section
                if kocom_section is not None:
                    kocom_info = config[kocom_section]
                    self.kocom_server       = self._clean_optional(kocom_info['server'])
                    self.kocom_port         = self._clean_optional(kocom_info['port'])
                    self.kocom_devicename   = self._clean_optional(kocom_info['device'])
                    kocom_subsection        = kocom_info['subdevice']
                    # wallpad
                    if kocom_subsection is None:
                        logger.critical("kocom section must have subdevice.")
                        return False
                    wallpad_devices = config[kocom_subsection]
                    for item in wallpad_devices:
                        self.device_list[item] = wallpad_devices[item]
                # aircon section
                if aircon_section is not None:
                    aircon_info = config[aircon_section]
                    self.aircon_server      = self._clean_optional(aircon_info['server'])
                    self.aircon_port        = self._clean_optional(aircon_info['port'])
                    self.aircon_devicename  = self._clean_optional(aircon_info['device'])
                # mqtt
                if cfg.CONF_MQTT not in config:
                    logger.critical("This application need MQTT config.")
                    return False
                mqtt_section = config[cfg.CONF_MQTT]
                for item in mqtt_section:
                    self.mqtt_anonymous = self._clean_optional(mqtt_section['anonymous'])
                    self.mqtt_server    = self._clean_optional(mqtt_section['server'])
                    self.mqtt_port      = self._clean_optional(mqtt_section['port'])
                    self.mqtt_id        = self._clean_optional(mqtt_section['username'])
                    self.mqtt_pw        = mqtt_section['password']
        except Exception as e:
            logger.critical(f"Error in reading config file.[{e}]")
            return False
        return True

    def is_device_enabled(self, device) -> bool:
        # NOTE: Intentionally always returns True.
        # Per-device disable via config is not used in practice.
        # To re-enable config-based filtering, remove 'True or' below.
        if True or self.device_list[device] == 'True':
            return True
        else:
            return False

    def has_mqtt_config(self) -> bool:
        return self._clean_optional(self.mqtt_server) != '' and self._has_valid_port(self.mqtt_port)

    def has_kocom_config(self) -> bool:
        return self._clean_optional(self.kocom_server) != '' and self._has_valid_port(self.kocom_port)

    def has_aircon_config(self) -> bool:
        return self._clean_optional(self.aircon_server) != '' and self._has_valid_port(self.aircon_port)

    def load_env_values(self):
        mqtt_server         = os.getenv('MQTT_SERVER_IP')
        mqtt_port           = os.getenv('MQTT_SERVER_PORT')
        kocom_server        = os.getenv('KOCOM_SERVER_IP')
        kocom_port          = os.getenv('KOCOM_SERVER_PORT')
        lgac_server         = os.getenv('LGAIRCON_SERVER_IP')
        lgac_port           = os.getenv('LGAIRCON_SERVER_PORT')
        log_level           = os.getenv('CONF_LOGLEVEL')
        log_partial_debug   = os.getenv('PARTIAL_DEBUG')
        temperature_adjust  = os.getenv('TEMPERATURE_ADJUST')

        logger.debug(f"Environment variables Loaded, "
                      f"mqtt_server={mqtt_server}, "
                      f"mqtt_port={mqtt_port}, "
                      f"kocom_server={kocom_server}, "
                      f"kocom_port={kocom_port}, "
                      f"lgac_server={lgac_server}, "
                      f"lgac_port={lgac_port}, "
                      f"log_level={log_level}"
                      f"temperature_adjust={temperature_adjust}")

        if mqtt_server:
            self.mqtt_server = self._clean_optional(mqtt_server)
        if mqtt_port:
            self.mqtt_port = self._clean_optional(mqtt_port)
        if kocom_server:
            self.kocom_server = self._clean_optional(kocom_server)
        if kocom_port:
            self.kocom_port = self._clean_optional(kocom_port)
        if lgac_server:
            self.aircon_server = self._clean_optional(lgac_server)
        if lgac_port:
            self.aircon_port = self._clean_optional(lgac_port)
        if log_level:
            self.log_level = self._clean_optional(log_level)

        if temperature_adjust:
            try:
                cfg.TEMPERATURE_ADJUST = float(temperature_adjust)
            except ValueError:
                logger.warning(f"Invalid TEMPERATURE_ADJUST[{temperature_adjust}] - keeping default {cfg.TEMPERATURE_ADJUST}")

        if log_partial_debug and log_partial_debug != 'false':
            set_partial_debug(True)

        rooms           = os.getenv('ROOMS')
        plug_numbers    = os.getenv('ROOMS_PLUG_NUMBERS')
        light_numbers   = os.getenv('ROOMS_LIGHT_NUMBERS')
        thermostats     = os.getenv('ROOMS_THERMOSTATS')
        aircons         = os.getenv('ROOMS_AIRCONS')

        # for debug test
        # rooms           = 'livingroom:bedroom:room1:room2:room3:kitchen'
        # plug_numbers    = '2:2:2:2:2:2'
        # light_numbers   = '3:0:0:0:0:0'
        # thermostats     = 'livingroom:bedroom:room1:room2:room3'
        # aircons         = 'livingroom:kitchen:bedroom:room2:room1:room3'

        if rooms:
            room_list: list[str] = rooms.split(':')
            room_dict = {f'{num:02x}': name for num, name in enumerate(room_list)}
            cfg.KOCOM_ROOM = room_dict

            if plug_numbers:
                plug_list: list[int] = list(map(int, plug_numbers.split(':')))
                plug_dict = {room_dict[f'{id:02x}']: num for id, num in enumerate(plug_list) if num > 0}
                cfg.KOCOM_PLUG_SIZE = plug_dict

            if light_numbers:
                light_list: list[int] = list(map(int, light_numbers.split(':')))
                light_dict = {room_dict[f'{id:02x}']: num for id, num in enumerate(light_list) if num > 0}
                cfg.KOCOM_LIGHT_SIZE = light_dict

        if thermostats:
            thermostat_list: list[str] = thermostats.split(':')
            thermostat_dict = {f'{num:02x}': name for num, name in enumerate(thermostat_list)}
            cfg.KOCOM_ROOM_THERMOSTAT = thermostat_dict

        if aircons:
            aircon_list: list[str] = aircons.split(':')
            aircon_dict = {f'{num:02x}': name for num, name in enumerate(aircon_list)}
            cfg.SYSTEM_ROOM_AIRCON = aircon_dict

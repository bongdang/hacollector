from __future__ import annotations

import os
from configparser import ConfigParser

import config as cfg
from classes.utils import Color, ColorLog


class MainConfig:
    def __init__(self) -> None:
        self.device_list: dict[str, str]    = {}
        self.kocom_server: str              = ''
        self.kocom_port: str                = '0'
        self.kocom_devicename: str          = ''
        self.aircon_server: str             = ''
        self.aircon_port: str               = '0'
        self.aircon_devicename: str         = ''
        self.mqtt_anonymous: str            = ''
        self.mqtt_server: str               = ''
        self.mqtt_port: str                 = ''
        self.mqtt_id: str                   = ''
        self.mqtt_pw: str                   = ''
        self.log_level: str                 = cfg.CONF_LOGLEVEL

    def read_config_file(self, config: ConfigParser) -> bool:
        color_log = ColorLog()
        try:
            # first, check RS485 Device
            rs485_devices = config[cfg.CONF_RS485_DEVICES]
            if rs485_devices is not None and len(rs485_devices) >= 1:
                kocom_section = None
                aircon_section = None
                for top_device in rs485_devices:
                    color_log.log(f"device section = {top_device}", Color.Cyan, ColorLog.Level.DEBUG)
                    if top_device == cfg.CONF_KOCOM_DEVICE_NAME.lower():
                        kocom_section = rs485_devices[top_device]
                    if top_device == cfg.CONF_AIRCON_DEVICE_NAME.lower():
                        aircon_section = rs485_devices[top_device]
                color_log.log(f"aircon section is {aircon_section}", Color.Blue, ColorLog.Level.DEBUG)
                if kocom_section is None and aircon_section is None:
                    color_log.log("kocom or aircon section must be exist.", Color.Red, ColorLog.Level.CRITICAL)
                    return False
                # KOCOM Device Section
                if kocom_section is not None:
                    kocom_info = config[kocom_section]
                    self.kocom_server       = kocom_info['server']
                    self.kocom_port         = kocom_info['port']
                    self.kocom_devicename   = kocom_info['device']
                    kocom_subsection        = kocom_info['subdevice']
                    # wallpad
                    if kocom_subsection is None:
                        color_log.log("kocom section must have subdevice.", Color.Red, ColorLog.Level.CRITICAL)
                        return False
                    wallpad_devices = config[kocom_subsection]
                    for item in wallpad_devices:
                        self.device_list[item] = wallpad_devices[item]
                # aircon section
                if aircon_section is not None:
                    aircon_info = config[aircon_section]
                    self.aircon_server      = aircon_info['server']
                    self.aircon_port        = aircon_info['port']
                    self.aircon_devicename  = aircon_info['device']
                # mqtt
                mqtt_section = config[cfg.CONF_MQTT]
                if mqtt_section is None:
                    color_log.log("This application need MQTT config.", Color.Red, ColorLog.Level.CRITICAL)
                    return False
                for item in mqtt_section:
                    self.mqtt_anonymous = mqtt_section['anonymous']
                    self.mqtt_server    = mqtt_section['server']
                    self.mqtt_port      = mqtt_section['port']
                    self.mqtt_id        = mqtt_section['username']
                    self.mqtt_pw        = mqtt_section['password']
        except Exception as e:
            color_log.log(f"Error in reading config file.[{e}]", Color.Red, ColorLog.Level.CRITICAL)
            return False
        return True

    def is_device_enabled(self, device) -> bool:
        if self.device_list[device] == 'True':
            return True
        else:
            return False

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

        color_log = ColorLog()
        color_log.log(f"Environment variables Loaded, "
                      f"mqtt_server={mqtt_server}, "
                      f"mqtt_port={mqtt_port}, "
                      f"kocom_server={kocom_server}, "
                      f"kocom_port={kocom_port}, "
                      f"lgac_server={lgac_server}, "
                      f"lgac_port={lgac_port}, "
                      f"log_level={log_level}"
                      f"temperature_adjust={temperature_adjust}",
                      Color.Cyan,
                      ColorLog.Level.DEBUG)

        if mqtt_server:
            self.mqtt_server = mqtt_server
        if mqtt_port:
            self.mqtt_port = mqtt_port
        if kocom_server:
            self.kocom_server = kocom_server
        if kocom_port:
            self.kocom_port = kocom_port
        if lgac_server:
            self.aircon_server = lgac_server
        if lgac_port:
            self.aircon_port = lgac_port
        if log_level:
            self.log_level = log_level

        if temperature_adjust:
            cfg.TEMPERATURE_ADJUST = temperature_adjust

        if log_partial_debug and log_partial_debug != 'false':
            color_log.set_partial_debug()

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

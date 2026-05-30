import asyncio
import json
# from typing import Callable

import config as cfg
from tcphandler.appconf_tcphandler import MainConfig
from loguru import logger
from consts import (AIRCON_DEFAULT_TEMP, DEVICE_AIRCON, MQTT_FAN_MODE,
                    MQTT_MODE, MQTT_SWING_MODE, MQTT_TARGET_TEMP, MQTT_CURRENT_TEMP,
                    PAYLOAD_FIXED, PAYLOAD_HIGH, PAYLOAD_LOW, PAYLOAD_MEDIUM,
                    PAYLOAD_OFF, PAYLOAD_ON, PAYLOAD_SILENT, PAYLOAD_STATUS,
                    PAYLOAD_SWING, DeviceType)
from devices.aircon import Aircon
from tcphandler.lgac485_tcp import LGACPacketHandler
from tcphandler.mqtt_tcp_aircon import AirconHandlerTroughMqtt


class GeneralAirconHandler:
    def __init__(self, config: MainConfig | None = None, need_mqtt: bool = False) -> None:
        self.SYSTEM_ROOM_AIRCON_REV = {v: k for k, v in cfg.SYSTEM_ROOM_AIRCON.items()}
        self.name                       = config.aircon_devicename if config is not None else 'TestAircon'
        self.enabled_device_list: list  = []
        self.aircon: list               = []
        self.type                       = None
        self.loop: asyncio.AbstractEventLoop
        self.read_error_count           = 0
        self.send_and_get_state         = False
        self.send_start_time: float     = 0.0
        self.prepare_enabled()
        self.init_real_handler(config, need_mqtt)

    def init_real_handler(self, config: MainConfig | None = None, needed_mqtt: bool = False):
        self.mqtt_aircon_handler = AirconHandlerTroughMqtt(config, LGACPacketHandler(config))      # type: ignore

        # connect mqtt for aircon if needed
        if needed_mqtt:
            self.mqtt_aircon_handler.connect_mqtt()

    def sync_close_socket(self, loop):
        pass

    def notify_to_ha_from_aircon_made_mqtt(self, device, command, room, opcmd, target_temp=AIRCON_DEFAULT_TEMP):
        try:
            data_dict = json.loads(opcmd)
            aircon_cmd = Aircon.Info(PAYLOAD_STATUS, '', '', '', AIRCON_DEFAULT_TEMP, AIRCON_DEFAULT_TEMP)
            if type(data_dict) is not dict:
                # color_log.log("It is only command.", Color.Red, ColorLog.Level.INFO)
                aircon_cmd.action = PAYLOAD_ON if opcmd != PAYLOAD_OFF else PAYLOAD_OFF
                aircon_cmd.opmode = opcmd
                aircon_cmd.target_temp = target_temp
            else:
                # color_log.log("It is Dict.", Color.Red, ColorLog.Level.INFO)
                aircon_cmd.action = PAYLOAD_ON if data_dict[MQTT_MODE] != PAYLOAD_OFF else PAYLOAD_OFF
                aircon_cmd.opmode = data_dict[MQTT_MODE]
                aircon_cmd.cur_temp = int(data_dict[MQTT_CURRENT_TEMP])
                aircon_cmd.target_temp = int(data_dict[MQTT_TARGET_TEMP])
                aircon_cmd.fanmove = data_dict[MQTT_SWING_MODE]
                aircon_cmd.fanmode = data_dict[MQTT_FAN_MODE]

            self.mqtt_aircon_handler.packet_handler.notify_to_homeassistant_aircon(device, room, aircon_cmd)
            logger.debug(f"Yes. {device},{command},{room},{opcmd} sent to HA.")
        except Exception as e:
            logger.info(f"Error [{e}]in handling packets [{opcmd}]")

    def prepare_enabled(self):
        for r_name in cfg.SYSTEM_ROOM_AIRCON.values():
            aircon = Aircon(r_name)
            aircon.set_initial_state()
            self.aircon.append(aircon)
        self.enabled_device_list.append((DeviceType.AIRCON, self.aircon))

    def get_room_aircon_number(self, instr: str) -> str:
        ret_str = self.SYSTEM_ROOM_AIRCON_REV.get(instr)
        return ret_str if ret_str is not None else ''

    def get_aircon(self, room_name: str) -> Aircon:
        if self.aircon is not None and len(self.aircon) >= 1:
            for item in self.aircon:
                assert isinstance(item, Aircon)
                if item.room_name == room_name:
                    return item
        raise ValueError(f"get_aircon error! room={room_name}")

    def handle_aircon_mqtt_message(self, topic: list[str], parameter: str) -> Aircon.Info | None:
        logger.info(f"LGAircon Action From MQTT.{topic}, = {parameter}")
        device_str = DEVICE_AIRCON
        room_str = topic[2]
        cmd_str = topic[3]
        try:
            opmode = ''
            aircon = self.get_aircon(room_str)
            assert isinstance(aircon, Aircon)
            if cmd_str == MQTT_MODE:
                opmode = parameter
                aircon.action = PAYLOAD_ON if parameter != PAYLOAD_OFF else PAYLOAD_OFF
            elif cmd_str == MQTT_SWING_MODE:
                if parameter == PAYLOAD_ON:
                    aircon.fanmove = PAYLOAD_SWING
                else:
                    aircon.fanmove = PAYLOAD_FIXED
            elif cmd_str == MQTT_FAN_MODE:
                if parameter in [PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_HIGH, PAYLOAD_SILENT]:
                    aircon.fanmode = parameter
                else:
                    aircon.fanmode = PAYLOAD_OFF
            elif cmd_str == MQTT_TARGET_TEMP:
                aircon.target_temp = int(float(parameter))

            logger.debug(f"act={aircon.action}, fanmove={aircon.fanmove}, fanspeed={aircon.fanmode}, "
                f"taregt_temp={aircon.target_temp}")
            if aircon.action in [PAYLOAD_OFF]:
                action_str = PAYLOAD_OFF
            else:
                action_str = PAYLOAD_ON
            # aircon_no = int(self.get_room_aircon_number(room_str))
            aircon_cmd = Aircon.Info(action_str, opmode, aircon.fanmove, aircon.fanmode, 0, aircon.target_temp)

            self.mqtt_aircon_handler.send_mqtt2tcp_aircon_command(room_str, aircon_cmd)
            self.notify_to_ha_from_aircon_made_mqtt(device_str, cmd_str, room_str, parameter, aircon.target_temp)
            # self.mqtt_aircon_handler.packet_handler.notify_to_homeassistant_aircon(DEVICE_AIRCON, room_str, aircon_cmd)

            logger.info(f"[From HA]{device_str}/{room_str}/set = [mode={aircon.action}, target_temp={aircon.target_temp}]")
            return aircon_cmd
        except Exception as e:
            logger.info(f"[From HA]Error [{e}] {topic} = {parameter}")
            return None

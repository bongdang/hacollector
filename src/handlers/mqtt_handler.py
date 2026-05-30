from __future__ import annotations

import json
# import os
from typing import TYPE_CHECKING, Callable

import paho.mqtt.client as pahomqtt

import config as cfg
from tcphandler.appconf_tcphandler import MainConfig
from loguru import logger
from consts import (DEVICE_AIRCON, DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS,
                    DEVICE_LIGHT, DEVICE_PLUG, DEVICE_SENSOR,
                    DEVICE_THERMOSTAT, DEVICE_WALLPAD, MQTT_CMD_T,
                    MQTT_CMD_TPL, MQTT_CONFIG, MQTT_CURRENT_TEMP,
                    MQTT_FAN_MODE, MQTT_ICON_AIRCON, MQTT_ICON_ELEVATOR,
                    MQTT_ICON_FAN, MQTT_ICON_GAS, MQTT_ICON_LIGHT,
                    MQTT_ICON_PLUG, MQTT_ICON_THERMOSTAT, MQTT_KEEP_ALIVE_SEC,
                    MQTT_MODE, MQTT_PAYLOAD, MQTT_PRESET_MODE, MQTT_SET,
                    MQTT_STAT, MQTT_STATE, MQTT_SWING_MODE, MQTT_TARGET_TEMP,
                    MQTT_TEMP, MQTT_VAL, PAYLOAD_COOL, PAYLOAD_DRY,
                    PAYLOAD_FAN_ONLY, PAYLOAD_HEAT, PAYLOAD_HIGH,
                    PAYLOAD_LOCKOFF, PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_OFF,
                    PAYLOAD_ON, PAYLOAD_STATE, PAYLOAD_SWING, RS485CHECK,
                    RS485COMMAND, RS485STAT, RS485TCP, SERVICE_NAME,
                    SW_VERSION_STRING, Command, DeviceType)

if TYPE_CHECKING:
    from devices.aircon import Aircon
else:
    from devices.aircon import Aircon


class Discovery:
    def __init__(self, pub, sub) -> None:
        self.pub: list[dict] = pub
        self.sub: list[tuple[str, int]] = sub

    def make_topic_and_payload_for_discovery(
        self, kind: str, room: str, device: str, icon_name: str, unique_id_suffix: str = ''
    ) -> tuple[str, dict]:
        common_topic_str = f'{cfg.HA_PREFIX}/{kind}/{room}'

        topic = f'{common_topic_str}_{device}/config'

        # default sensor items.
        payload = {
            'name': f'{SERVICE_NAME}_{room}_{device}',
            'uniq_id': f'{SERVICE_NAME}_{room}_{device}{unique_id_suffix}',
            'device': {
                'name': f'Kocom {room} {device}',
                'ids': f'kocom_{room}_{device}',
                'mf': 'KOCOM',
                'mdl': 'Wallpad',
                'sw': SW_VERSION_STRING
            }
        }
        if icon_name != '':
            payload['ic'] = icon_name

        if device != DEVICE_THERMOSTAT:
            if device == DEVICE_GAS:
                payload[f'{MQTT_STAT}_t'] = f'{common_topic_str}_{DEVICE_GAS}/{MQTT_STATE}'
            elif device == DEVICE_FAN:
                pass
            elif device == DEVICE_SENSOR:
                payload[f'{MQTT_STAT}_t'] = f'{common_topic_str}_{DEVICE_SENSOR}/{MQTT_STATE}'
            else:
                payload[f'{MQTT_STAT}_t'] = f'{common_topic_str}/{MQTT_STATE}'

        if device in [DEVICE_ELEVATOR, DEVICE_GAS]:
            payload[f'{MQTT_VAL}_tpl']              = '{{ value_json.' + f'{device}' + ' }}'
        elif device == DEVICE_FAN:
            topic_header                            = f'{common_topic_str}_{DEVICE_FAN}'
            topic                                   = f'{topic_header}/config'
            SET_MODE                                = MQTT_PRESET_MODE
            payload[f'{SET_MODE}s']                 = [PAYLOAD_OFF, PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_HIGH]
            payload[f'{MQTT_CMD_T}']                = f'{topic_header}/set'
            payload[f'{MQTT_CMD_TPL}']              = '{{ value }}'
            payload[f'{SET_MODE}_command_topic']    = f'{topic_header}/{SET_MODE}_set'
            payload[f'{SET_MODE}_command_template'] = '{ "preset_mode": "{{ value }}" }'
            payload[f'{SET_MODE}_state_topic']      = f'{topic_header}/{SET_MODE}_state'
            payload[f'{SET_MODE}_value_template']   = '{{ value_json.preset_mode }}'
            payload['optimistic']                   = 'true'
        elif device == DEVICE_SENSOR:
            payload['unit_of_measurement']          = 'ppm'
            payload[f'{MQTT_VAL}_tpl']              = '{{ value_json.co2 }}'
        elif device == DEVICE_THERMOSTAT:
            payload[f'{MQTT_MODE}_{MQTT_CMD_T}']    = f'{common_topic_str}/{MQTT_MODE}'
            payload[f'{MQTT_MODE}_stat_t']          = f'{common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_MODE}_stat_tpl']        = '{{ value_json.mode }}'
            payload[f'{MQTT_TEMP}_{MQTT_CMD_T}']    = f'{common_topic_str}/{MQTT_TARGET_TEMP}'
            payload[f'{MQTT_TEMP}_stat_t']          = f'{common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_TEMP}_stat_tpl']        = '{{ value_json.target_temp }}'
            payload[f'curr_{MQTT_TEMP}_t']          = f'{common_topic_str}/{MQTT_STATE}'
            payload[f'curr_{MQTT_TEMP}_tpl']        = '{{ value_json.current_temp }}'
            payload[f'min_{MQTT_TEMP}']             = 5
            payload[f'max_{MQTT_TEMP}']             = 40
            payload[f'{MQTT_TEMP}_step']            = 1
            payload[f'{MQTT_MODE}s']                = [PAYLOAD_OFF, PAYLOAD_HEAT, PAYLOAD_FAN_ONLY]
        elif device == DEVICE_AIRCON:
            aircon_common_topic_str                 = f'{cfg.CONF_AIRCON_DEVICE_NAME}/{kind}/{room}'
            aircon_common_id_str                    = f'{cfg.CONF_AIRCON_DEVICE_NAME}_{room}_{device}'
            payload["device"] = {
                'name': f'{cfg.CONF_AIRCON_DEVICE_NAME} {room} {device}',
                'ids': aircon_common_id_str,
                'mf': 'LG',
                'mdl': 'System Aircon',
                'sw': SW_VERSION_STRING
            }
            payload['name']                         = aircon_common_id_str
            payload['uniq_id']                      = aircon_common_id_str
            payload[f'{MQTT_MODE}_stat_t']          = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_MODE}_stat_tpl']        = '{{ value_json.mode }}'
            payload[f'{MQTT_MODE}_{MQTT_CMD_T}']    = f'{aircon_common_topic_str}/{MQTT_MODE}'
            payload[f'{MQTT_MODE}s']                = [PAYLOAD_OFF, PAYLOAD_COOL, PAYLOAD_DRY, PAYLOAD_FAN_ONLY]
            payload[f'{MQTT_TEMP}_stat_t']          = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_TEMP}_stat_tpl']        = '{{ value_json.target_temp }}'
            payload[f'{MQTT_TEMP}_step']            = 1
            payload[f'{MQTT_TEMP}_{MQTT_CMD_T}']    = f'{aircon_common_topic_str}/{MQTT_TARGET_TEMP}'
            payload[f'min_{MQTT_TEMP}']             = 18
            payload[f'max_{MQTT_TEMP}']             = 33
            payload[f'curr_{MQTT_TEMP}_t']          = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'curr_{MQTT_TEMP}_tpl']        = '{{ value_json.current_temp }}'
            payload[f'{MQTT_FAN_MODE}_stat_t']      = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_FAN_MODE}_stat_tpl']    = '{{ value_json.fan_mode }}'
            payload[f'{MQTT_FAN_MODE}_{MQTT_CMD_T}'] = f'{aircon_common_topic_str}/{MQTT_FAN_MODE}'
            payload[f'{MQTT_FAN_MODE}s']            = [PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_HIGH, PAYLOAD_OFF]
            payload[f'{MQTT_SWING_MODE}_stat_t']    = f'{aircon_common_topic_str}/{MQTT_STATE}'
            payload[f'{MQTT_SWING_MODE}_stat_tpl']  = '{{ value_json.swing_mode }}'
            payload[f'{MQTT_SWING_MODE}_{MQTT_CMD_T}'] \
                = f'{aircon_common_topic_str}/{MQTT_SWING_MODE}'
            payload[f'{MQTT_SWING_MODE}s']          = [PAYLOAD_ON, PAYLOAD_OFF]
        elif kind in [cfg.HA_SWITCH, cfg.HA_LIGHT]:
            payload[f"{MQTT_STAT}_val_tpl"]         = '{{ value_json.' + str(device) + ' }}'

        if kind in [cfg.HA_SWITCH, cfg.HA_LIGHT]:
            payload[MQTT_CMD_T]                     = f'{common_topic_str}_{device}/{MQTT_SET}'

        if kind in [cfg.HA_SWITCH, cfg.HA_LIGHT]:
            payload[f"{MQTT_PAYLOAD}_on"]            = PAYLOAD_ON 
            payload[f"{MQTT_PAYLOAD}_off"]          = PAYLOAD_OFF

        return topic, payload

    def discovery_elevator(self, remove: bool, enabled_device=None) -> None:
        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
            kind=cfg.HA_SWITCH, room=DEVICE_WALLPAD, device=DEVICE_ELEVATOR, icon_name=MQTT_ICON_ELEVATOR
        )
        self.sub.append((ha_topic, 0))
        self.sub.append((ha_payload[MQTT_CMD_T], 0))
        if remove:
            self.pub.append({ha_topic: ''})
        else:
            self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_gas(self, remove: bool, enabled_device=None) -> None:
        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
            kind=cfg.HA_SWITCH, room=DEVICE_WALLPAD, device=DEVICE_GAS, icon_name=MQTT_ICON_GAS
        )
        self.sub.append((ha_topic, 0))
        self.sub.append((ha_payload[MQTT_CMD_T], 0))
        if remove:
            self.pub.append({ha_topic: ''})
        else:
            self.pub.append({ha_topic: json.dumps(ha_payload)})

        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
            kind=cfg.HA_SENSOR,
            room=DEVICE_WALLPAD,
            device=DEVICE_GAS,
            icon_name=MQTT_ICON_GAS,
            unique_id_suffix='_sensor'
        )
        self.sub.append((ha_topic, 0))
        if remove:
            self.pub.append({ha_topic: ''})
        else:
            self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_fan(self, remove: bool, enabled_device=None) -> None:
        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
            kind=cfg.HA_FAN, room=DEVICE_WALLPAD, device=DEVICE_FAN, icon_name=MQTT_ICON_FAN
        )
        self.sub.append((ha_topic, 0))
        self.sub.append((ha_payload[MQTT_CMD_T], 0))
        self.sub.append((ha_payload[f'{MQTT_PRESET_MODE}_command_topic'], 0))
        if remove:
            self.pub.append({ha_topic: ''})
        else:
            self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_fan_sensor(self, remove: bool, enabled_device=None) -> None:
        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
            kind=cfg.HA_SENSOR, room=DEVICE_WALLPAD, device=DEVICE_SENSOR, icon_name=MQTT_ICON_FAN
        )
        self.sub.append((ha_topic, 0))
        if remove:
            self.pub.append({ha_topic: ''})
        else:
            self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_thermostat(self, remove: bool, enabled_device: list | None = None) -> None:
        from devices.thermostat import Thermostat

        assert isinstance(enabled_device, list)
        for room_thermostats in enabled_device:
            if isinstance(room_thermostats, Thermostat):
                room_name = room_thermostats.room_name
                if room_name is not None:
                    ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
                        kind=cfg.HA_CLIMATE, room=room_name, device=DEVICE_THERMOSTAT,
                        icon_name=MQTT_ICON_THERMOSTAT
                    )
                    self.sub.append((ha_topic, 0))
                    self.sub.append((ha_payload[f'{MQTT_MODE}_{MQTT_CMD_T}'], 0))
                    self.sub.append((ha_payload[f'{MQTT_TEMP}_{MQTT_CMD_T}'], 0))
                    if remove:
                        self.pub.append({ha_topic: ''})
                    else:
                        self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_aircon(self, remove: bool, enabled_device: list | None = None) -> None:
        from devices.aircon import Aircon

        assert isinstance(enabled_device, list)
        for room_aircon in enabled_device:
            if isinstance(room_aircon, Aircon):
                room_name = room_aircon.room_name
                if room_name is not None:
                    ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
                        kind=cfg.HA_CLIMATE, room=room_name, device=DEVICE_AIRCON, icon_name=MQTT_ICON_AIRCON
                    )
                    self.sub.append((ha_topic, 0))
                    self.sub.append((ha_payload[f'{MQTT_MODE}_{MQTT_CMD_T}'], 0))
                    self.sub.append((ha_payload[f'{MQTT_TEMP}_{MQTT_CMD_T}'], 0))
                    self.sub.append((ha_payload[f'{MQTT_FAN_MODE}_{MQTT_CMD_T}'], 0))
                    self.sub.append((ha_payload[f'{MQTT_SWING_MODE}_{MQTT_CMD_T}'], 0))
                    if remove:
                        self.pub.append({ha_topic: ''})
                    else:
                        self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_light(self, remove: bool, enabled_device: list | None = None) -> None:
        from devices.light import Light

        assert isinstance(enabled_device, list)
        for room_lights in enabled_device:
            if isinstance(room_lights, Light):
                room_name = room_lights.room_name
                if room_name is not None:
                    for light_name, _ in room_lights.light_list:
                        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
                            kind=cfg.HA_LIGHT, room=room_name, device=light_name, icon_name=MQTT_ICON_LIGHT
                        )

                        self.sub.append((ha_topic, 0))
                        self.sub.append((ha_payload[MQTT_CMD_T], 0))
                        if remove:
                            self.pub.append({ha_topic: ''})
                        else:
                            self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_plug(self, remove: bool, enabled_device: list | None = None) -> None:
        from devices.plug import Plug

        assert isinstance(enabled_device, list)
        for room_plugs in enabled_device:
            if isinstance(room_plugs, Plug):
                room_name = room_plugs.room_name
                if room_name is not None:
                    for plug_name, _ in room_plugs.plug_list:
                        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
                            kind=cfg.HA_SWITCH, room=room_name, device=plug_name, icon_name=MQTT_ICON_PLUG
                        )
                        self.sub.append((ha_topic, 0))
                        self.sub.append((ha_payload[MQTT_CMD_T], 0))
                        if remove:
                            self.pub.append({ha_topic: ''})
                        else:
                            self.pub.append({ha_topic: json.dumps(ha_payload)})

    def make_discovery_list(self, dev_name: DeviceType, enabled_device: list, remove: bool) -> None:
        if dev_name == DeviceType.ELEVATOR:
            self.discovery_elevator(remove)
        elif dev_name == DeviceType.GAS:
            self.discovery_gas(remove)
        elif dev_name == DeviceType.FAN:
            self.discovery_fan(remove)
            self.discovery_fan_sensor(remove)
        elif dev_name == DeviceType.LIGHT:
            self.discovery_light(remove, enabled_device)
        elif dev_name == DeviceType.PLUG:
            self.discovery_plug(remove, enabled_device)
        elif dev_name == DeviceType.THERMOSTAT:
            self.discovery_thermostat(remove, enabled_device)
        elif dev_name == DeviceType.AIRCON:
            self.discovery_aircon(remove, enabled_device)


class MqttHandler:
    def __init__(self, config: MainConfig) -> None:
        self.server                                 = config.mqtt_server
        self.port                                   = int(config.mqtt_port)
        self.anonymous                              = config.mqtt_anonymous
        self.id                                     = config.mqtt_id
        self.pw                                     = config.mqtt_pw
        self.mqtt_client                            = None
        self.start_discovery                        = False
        self.mqtt_connect_error                     = False
        self.subscribe_list: list[tuple[str, int]]  = []
        self.publish_list: list[dict]               = []
        self.ignore_handling: bool                  = False

    def set_enabled_list(self, enabled_list: list) -> None:
        self.enabled_list = enabled_list

    def set_kocom_mqtt_handler(self, handle_wallpad_mqtt_message: Callable[[list[str], str], None]) -> None:
        self.kocom_mqtt_handler = handle_wallpad_mqtt_message

    def set_aircon_mqtt_handler(self, handle_aircon_mqtt_message: Callable[[list[str], str], None]) -> None:
        self.aircon_mqtt_handler = handle_aircon_mqtt_message

    def set_kocom_tcp2mqtt_handler(self, handle_kocom_tcp_message: Callable[[str, str, str, str], None]) -> None:
        self.kocom_tcp_handler = handle_kocom_tcp_message

    def set_handle_mqtt_from_tcp_aircon(self, handle_aircon_tcp_message: Callable[[str, str, str, str], None]) -> None:
        self.handle_mqtt_from_tcp_aircon = handle_aircon_tcp_message

    def set_reconnect_action(self, reconnect_action: Callable[[], None]) -> None:
        self.reconnect_action = reconnect_action

    def set_ignore_handling(self):
        self.ignore_handling = True

    def connect_mqtt(self) -> None:
        is_anonymous = True if self.anonymous == 'True' else False
        server = self.server
        port = self.port
        self.mqtt_client = pahomqtt.Client()
        self.mqtt_client.on_message = self.on_message
        # self.mqtt_client.on_publish = self.on_publish
        self.mqtt_client.on_subscribe = self.on_subscribe
        self.mqtt_client.on_connect = self.on_connect

        if server == '':
            logger.info(f"{cfg.CONF_MQTT} Check Config! Server is empty")
            return
        if not is_anonymous and self.id and self.pw:
            self.mqtt_client.username_pw_set(username=self.id, password=self.pw)
            logger.info(f"{cfg.CONF_MQTT} Configuration: [{server}:{port}] (authenticated)")
        else:
            if not is_anonymous and (self.id == '' or self.pw == ''):
                logger.info(f"{cfg.CONF_MQTT} Credentials missing, falling back to anonymous connection")
            logger.info(f"{cfg.CONF_MQTT} Configuration: [{server}:{port}] (anonymous)")

        logger.info("Connectting MQTT...")
        self.mqtt_client.connect(server, port, MQTT_KEEP_ALIVE_SEC)
        self.mqtt_client.loop_start()
        try:
            self.initialize_tcp_topics()
        except Exception:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            raise

    def cleanup(self) -> None:
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.mqtt_connect_error = True

    def handle_message_from_mqtt(self, topic: list[str], payload: str) -> None:
        logger.debug(f"MQTT ## topic = [{topic}], payload[{payload}]")
        if not (type(topic) is list and len(topic) == 4):
            logger.info("*** Parse Error! topic is not list or not 3 items!")
            return

        if MQTT_CONFIG in topic:
            logger.debug("This topic is for HA CONFIGURATION. Not ME.!")
            return

        (header, device, command, room) = topic
        if header == RS485TCP:
            if command == RS485STAT:
                if device != DEVICE_AIRCON:
                    logger.debug(f"***>> From TCP2MQTT {device},{command},{room},{payload}")
                    self.kocom_tcp_handler(device, command, room, payload)
                elif device == DEVICE_AIRCON:
                    logger.debug(f"***>> From TCP2MQTT_AIRCON_IN_MAIN {device},{command},{room},{payload}")
                    self.handle_mqtt_from_tcp_aircon(device, command, room, payload)
            elif command == RS485COMMAND:
                logger.debug("This topic is for Sending to RS485. Not ME.!")
        else:
            if topic[0] == cfg.CONF_AIRCON_DEVICE_NAME:
                ret = self.aircon_mqtt_handler(topic, payload)
                if ret is not None:
                    assert isinstance(ret, Aircon.Info)
                    self.send_aircon_state_to_homeassistant(device, room, ret)
            else:
                self.kocom_mqtt_handler(topic, payload)

    def homeassistant_device_discovery(self, initial: bool = False, remove: bool = False) -> None:

        self.subscribe_list = []
        self.subscribe_list.append((cfg.HA_CALLBACK_MAIN + '/' + cfg.HA_CALLBACK_BRIDGE + '/#', 0))
        self.publish_list = []

        logger.info("** Starting Devices Discovery.")
        discovery = Discovery(self.publish_list, self.subscribe_list)

        logger.debug(f"enabled list = [{self.enabled_list}]")
        for dev_name, enabled_device in self.enabled_list:
            logger.debug(f"dev_name = {dev_name}, device = {enabled_device}")
            discovery.make_discovery_list(DeviceType(dev_name), enabled_device, remove)

        if self.mqtt_client:
            if initial:
                self.mqtt_client.subscribe(self.subscribe_list)
            for ha in self.publish_list:
                for topic, payload in ha.items():
                    self.mqtt_client.publish(topic, payload)

        if self.start_discovery:
            self.start_discovery = False

    def make_topic_string(self, prefix: str, main: str, sub: str, item: str, postfix: str | None = None) -> str:
        if postfix is None:
            return f'{prefix}/{main}/{sub}/{item}'
        return f'{prefix}/{main}/{sub}_{postfix}/{item}'

    def send_state_to_homeassistant(self, device: str, room: str, value: dict) -> None:

        def get_ha_device_string(device: str):
            if device in [DEVICE_ELEVATOR, DEVICE_PLUG]:
                return cfg.HA_SWITCH
            elif device in [DEVICE_THERMOSTAT, DEVICE_AIRCON]:
                return cfg.HA_CLIMATE
            elif device == DEVICE_LIGHT:
                return cfg.HA_LIGHT
            elif device == DEVICE_FAN:
                return cfg.HA_FAN
            elif device == DEVICE_GAS:
                return cfg.HA_GAS
            elif device == DEVICE_SENSOR:
                return cfg.HA_SENSOR
            else:
                logger.debug(f"Wrong device matching to HA = [{device}]")
                return

        logger.debug(f"Trying to send states to HA : d=[{device}], v=[{value}]")

        if self.mqtt_client:
            v_value = json.dumps(value)

            if device == DEVICE_GAS:
                # gas state send to item sensor and switch - KKS
                topic = self.make_topic_string(cfg.HA_PREFIX, cfg.HA_SENSOR, room, PAYLOAD_STATE, DEVICE_GAS)
                self.mqtt_client.publish(topic, v_value)
                topic = self.make_topic_string(cfg.HA_PREFIX, cfg.HA_SWITCH, room, PAYLOAD_STATE, DEVICE_GAS)
            else:
                # others only send one - KKS
                ha_device = get_ha_device_string(device)
                if ha_device is not None:
                    if device == DEVICE_AIRCON:
                        prefix = cfg.CONF_AIRCON_DEVICE_NAME
                    else:
                        prefix = cfg.HA_PREFIX
                    if ha_device == cfg.HA_SENSOR:
                        topic = self.make_topic_string(prefix, ha_device, DEVICE_WALLPAD, PAYLOAD_STATE, DEVICE_SENSOR)
                    elif ha_device == cfg.HA_FAN:
                        command_set = f'{MQTT_PRESET_MODE}_state'
                        topic = self.make_topic_string(prefix, ha_device, DEVICE_WALLPAD, command_set, DEVICE_FAN)
                    else:
                        if len(room) != 0:
                            topic = self.make_topic_string(prefix, ha_device, room, PAYLOAD_STATE)
                        else:
                            topic = None
                else:
                    topic = None

            if topic is not None:
                self.mqtt_client.publish(topic, v_value)
                logger.debug(f"[To HA]{topic} = {v_value}")
        else:
            logger.critical("MQTT handle is invalid!")

    def send_aircon_state_to_homeassistant(self, dev_str: str, room_str: str, aircon_info: Aircon.Info):
        if aircon_info.action in [PAYLOAD_OFF, PAYLOAD_LOCKOFF]:
            mode = PAYLOAD_OFF
        else:
            mode = aircon_info.opmode
        logger.debug(f"current action = {aircon_info.action}, opmode = {aircon_info.opmode} => opmode=[{mode}]")
        if aircon_info.fanmove == PAYLOAD_SWING:
            swing = PAYLOAD_ON
        else:
            swing = PAYLOAD_OFF
        value = {
            f'{MQTT_MODE}': f'{mode}',
            f'{MQTT_SWING_MODE}': f'{swing}',
            f'{MQTT_FAN_MODE}': f'{aircon_info.fanmode}',
            f'{MQTT_CURRENT_TEMP}': f'{int(aircon_info.cur_temp)}',
            f'{MQTT_TARGET_TEMP}': f'{aircon_info.target_temp}'
        }
        logger.debug(f"new aircon status = [{value}]")
        self.send_state_to_homeassistant(dev_str, room_str, value)

    def on_publish(self, client, obj, mid):
        logger.debug(f"Publish: {str(mid)}")

    def on_subscribe(self, client, obj, mid, granted_qos):
        logger.debug(f"Subscribed: {str(mid)} {str(granted_qos)}")

    def on_connect(self, client, userdata, flags, rc):
        if int(rc) == 0:
            logger.info("[MQTT] connected OK")
            # start_discovery triggers HA bridge re-subscribe + discovery republish
            # via the hub scan loop (hub.py). That path covers only the bridge topic.
            self.start_discovery = True
            # paho restores no subscriptions after an automatic reconnect, and the
            # discovery path above does not re-subscribe the RS485 state topics. Without
            # this, a broker bounce silently stops the hub from receiving tcp2mqtt /
            # tcp2mqtt_aircon state until process restart. (Duplicate SUBSCRIBE is a no-op.)
            if self.mqtt_client is not None:
                self.initialize_tcp_topics()
            return
        elif int(rc) == 1:
            logger.info("[MQTT] 1: Connection refused – incorrect protocol version")
        elif int(rc) == 2:
            logger.info("[MQTT] 2: Connection refused – invalid client identifier")
        elif int(rc) == 3:
            logger.info("[MQTT] 3: Connection refused – server unavailable")
        elif int(rc) == 4:
            logger.info("[MQTT] 4: Connection refused – bad username or password")
        elif int(rc) == 5:
            logger.info("[MQTT] 5: Connection refused – not authorised")
        else:
            logger.info(f"[MQTT] {rc} : Connection refused")
        self.mqtt_connect_error = True

    # handle message form homeassistant through mqtt
    def on_message(self, client, obj, msg: pahomqtt.MQTTMessage):
        if not self.ignore_handling:
            rcv_topic = msg.topic.split('/')
            rcv_payload = msg.payload.decode()

            if (
                'config' in rcv_topic and (rcv_topic[0], 
                                           rcv_topic[1], 
                                           rcv_topic[2]) == (cfg.HA_CALLBACK_MAIN, 
                                                             cfg.HA_CALLBACK_BRIDGE, 
                                                             'config')
            ):
                if rcv_topic[3] == 'log_level':
                    if rcv_payload in ['info', 'debug', 'warn']:
                        color_log.set_level(rcv_payload)
                    logger.info(f"[From HA]Set Loglevel to {rcv_payload}")
                    return
                elif rcv_topic[3] == 'restart':
                    self.homeassistant_device_discovery()
                    logger.info("[From HA]HomeAssistant Restart")
                    return
                elif rcv_topic[3] == 'remove':
                    self.homeassistant_device_discovery(remove=True)
                    logger.info("[From HA]HomeAssistant Remove")
                    return
                elif rcv_topic[3] == 'reconnect':
                    self.reconnect_action()
                    logger.info("[From HA]Reconnect EW11(s) Called!")
                    return
                elif rcv_topic[3] == 'check_alive':
                    logger.info("[From HA]Handler(hacollector) is alive!")
                    return
                elif rcv_topic[3] == 'restart_aircon':
                    # os.system('docker restart tcp2mqtt_aircon')
                    logger.info("[From HA]Restart Aircon Called!")
                    return
            elif not self.start_discovery:
                self.handle_message_from_mqtt(rcv_topic, rcv_payload)
                return
            logger.debug(f"Message: {msg.topic} = {rcv_payload}")

    def initialize_tcp_topics(self):
        self.subscribe_list = []
#        self.subscribe_list.append((f'{RS485TCP}/#', 0))
        self.publish_list = []

        logger.info("** Starting RS485 mqtt topics.")

        tcp485_list = [
            f"{RS485TCP}/{DEVICE_LIGHT}",
            f"{RS485TCP}/{DEVICE_THERMOSTAT}",
            f"{RS485TCP}/{DEVICE_PLUG}",
            f"{RS485TCP}/{DEVICE_FAN}",
            f"{RS485TCP}/{DEVICE_GAS}",
            f"{RS485TCP}/{DEVICE_ELEVATOR}",
            f"{RS485TCP}/{DEVICE_SENSOR}",
            f"{RS485TCP}/{DEVICE_AIRCON}",
        ]

        if self.mqtt_client:
            # subs
            for item in tcp485_list:
                topic = f'{item}/#'
                logger.info(f"subscribing : {topic}")
                self.subscribe_list.append((topic, 0))

            # pubs
            # self.publish_list.append({ha_topic: json.dumps(ha_payload)})

            self.mqtt_client.subscribe(self.subscribe_list)

    def send_mqtt2tcp_command(self, device, room, payload, cmd):
        logger.debug(f"MQTT2TCP Command: {device},{room},{payload}")
        if self.mqtt_client:
            if cmd == Command.CHECK:
                topic = f'{RS485TCP}/{device}/{RS485CHECK}/{room}'
            else:
                topic = f'{RS485TCP}/{device}/{RS485COMMAND}/{room}'
            self.mqtt_client.publish(topic, payload)

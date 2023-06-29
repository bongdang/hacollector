from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

import paho.mqtt.client as pahomqtt

import config as cfg
from classes.appconf import MainConfig
from classes.utils import Color, ColorLog
from consts import (DEVICE_AIRCON, DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS,
                    DEVICE_LIGHT, DEVICE_PLUG, DEVICE_SENSOR,
                    DEVICE_THERMOSTAT, DEVICE_WALLPAD, MQTT_CMD_T, MQTT_CONFIG,
                    MQTT_CURRENT_TEMP, MQTT_FAN_MODE, MQTT_FAN_SPEED,
                    MQTT_ICON_AIRCON, MQTT_ICON_ELEVATOR, MQTT_ICON_FAN,
                    MQTT_ICON_GAS, MQTT_ICON_LIGHT, MQTT_ICON_PLUG,
                    MQTT_ICON_THERMOSTAT, MQTT_MODE, MQTT_PAYLOAD, MQTT_SET,
                    MQTT_STAT, MQTT_STATE, MQTT_SWING_MODE, MQTT_TARGET_TEMP,
                    MQTT_TEMP, MQTT_VAL, PAYLOAD_COOL, PAYLOAD_DRY,
                    PAYLOAD_FAN_ONLY, PAYLOAD_HEAT, PAYLOAD_HIGH,
                    PAYLOAD_LOCKOFF, PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_OFF,
                    PAYLOAD_ON, PAYLOAD_STATE, PAYLOAD_SWING, SERVICE_NAME,
                    SW_VERSION_STRING, DeviceType)

if TYPE_CHECKING:
    from classes.aircon import Aircon


class Discovery:
    def __init__(self, pub, sub) -> None:
        self.pub: list[dict] = pub
        self.sub: list[tuple[str, int]] = sub

    def make_topic_and_payload_for_discovery(
        self, kind: str, room: str, device: str, icon_name: str
    ) -> tuple[str, dict]:
        common_topic_str = f'{cfg.HA_PREFIX}/{kind}/{room}'

        topic = f'{common_topic_str}_{device}/config'

        # default sensor items.
        payload = {
            'name': f'{SERVICE_NAME}_{room}_{device}',
            'uniq_id': f'{SERVICE_NAME}_{room}_{device}',
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
            # elif device == DEVICE_FAN:
            #    payload[f'{MQTT_STAT}_t'] = f'{common_topic_str}_{DEVICE_FAN}/{MQTT_STATE}'
            elif device == DEVICE_SENSOR:
                payload[f'{MQTT_STAT}_t'] = f'{common_topic_str}_{DEVICE_SENSOR}/{MQTT_STATE}'
            else:
                payload[f'{MQTT_STAT}_t'] = f'{common_topic_str}/{MQTT_STATE}'

        if device in [DEVICE_ELEVATOR, DEVICE_GAS]:
            payload[f'{MQTT_VAL}_tpl']              = '{{ value_json.' + f'{device}' + ' }}'
        elif device == DEVICE_FAN:
            payload['speed_range_min']              = 1
            payload['speed_range_max']              = 4
            payload['state_value_template']         = "{{ value_json.fan_mode }}"
            payload[MQTT_CMD_T]                     = f'{common_topic_str}/{MQTT_FAN_MODE}'
            payload['command_template']             = '{{ value_json.fan_mode }}'
            payload['percentage_state_topic']       = f'{common_topic_str}/{MQTT_FAN_MODE}'
            payload['percentage_value_template']    = "{{ value_json.fan_speed }}"
            payload['percentage_command_topic']     = f'{common_topic_str}/{MQTT_FAN_SPEED}'
            payload['percentage_command_template']  = "{ 'fan_speed': {{ value }} }"
            # payload['unit_of_measurement']          = 'speed'
            # payload['value_template']               = '{{ value_json.fan_mode }}'
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
            payload[f"{MQTT_PAYLOAD}_on"]           = PAYLOAD_ON
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
            kind=cfg.HA_SENSOR, room=DEVICE_WALLPAD, device=DEVICE_GAS, icon_name=MQTT_ICON_GAS
        )
        self.sub.append((ha_topic, 0))
        self.pub.append({ha_topic: json.dumps(ha_payload)})

    def discovery_fan(self, remove: bool, enabled_device=None) -> None:
        ha_topic, ha_payload = self.make_topic_and_payload_for_discovery(
            kind=cfg.HA_FAN, room=DEVICE_WALLPAD, device=DEVICE_FAN, icon_name=MQTT_ICON_FAN
        )
        self.sub.append((ha_topic, 0))
#        self.sub.append((ha_payload[MQTT_CMD_T], 0))
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
        from classes.thermostat import Thermostat

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
        from classes.aircon import Aircon

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
        from classes.light import Light

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
        from classes.plug import Plug

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

    def set_enabled_list(self, enabled_list: list):
        self.enabled_list = enabled_list

    def set_kocom_mqtt_handler(self, handle_wallpad_mqtt_message):
        self.kocom_mqtt_handler: Callable[[list[str], str], None] = handle_wallpad_mqtt_message

    def set_aircon_mqtt_handler(self, handle_aircon_mqtt_message):
        self.aircon_mqtt_handler: Callable[[list[str], str], None] = handle_aircon_mqtt_message

    def set_reconnect_action(self, reconnect_action):
        self.reconnect_action: Callable[[], None] = reconnect_action

    def set_ignore_handling(self):
        self.ignore_handling = True

    def connect_mqtt(self) -> None:
        color_log = ColorLog()
        is_anonymous = True if self.anonymous == 'True' else False
        server = self.server
        port = self.port
        self.mqtt_client = pahomqtt.Client()
        self.mqtt_client.on_message = self.on_message
        # self.mqtt_client.on_publish = self.on_publish
        self.mqtt_client.on_subscribe = self.on_subscribe
        self.mqtt_client.on_connect = self.on_connect

        if not is_anonymous:
            username = self.id
            password = self.pw
            if server == '' or username == '' or password == '':
                color_log.log(
                    f"{cfg.CONF_MQTT} Check Config! Server[{server}] ID[{username}] PW[{password}]",
                    Color.Red
                )
                return
            self.mqtt_client.username_pw_set(username=username, password=password)
        else:
            color_log.log(f"{cfg.CONF_MQTT} Configuration: [{server}:{port}]")

        color_log.log("Connectting MQTT...", Color.Yellow)
        self.mqtt_client.connect(server, port, 60)
        self.mqtt_client.loop_start()

    def cleanup(self) -> None:
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.mqtt_connect_error = True

    def handle_message_from_mqtt(self, topic: list[str], payload: str) -> None:
        color_log = ColorLog()
        color_log.log(f"MQTT ## topic = [{topic}], payload[{payload}]", Color.White, ColorLog.Level.DEBUG)
        if not (type(topic) == list and len(topic) == 4):
            color_log.log("*** Parse Error! topic is not list or not 3 items!", Color.Red)
            return

        if MQTT_CONFIG in topic:
            color_log.log("This topic is for HA CONFIGURATION. Not ME.!", Color.Green, ColorLog.Level.DEBUG)
            return

        if topic[0] == cfg.CONF_AIRCON_DEVICE_NAME:
            self.aircon_mqtt_handler(topic, payload)
        else:
            self.kocom_mqtt_handler(topic, payload)

    def homeassistant_device_discovery(self, initial: bool = False, remove: bool = False) -> None:

        self.subscribe_list = []
        self.subscribe_list.append((cfg.HA_CALLBACK_MAIN + '/' + cfg.HA_CALLBACK_BRIDGE + '/#', 0))
        self.publish_list = []

        color_log = ColorLog()
        color_log.log("** Starting Devices Discovery.", Color.Yellow)
        discovery = Discovery(self.publish_list, self.subscribe_list)

        color_log.log(f"enabled list = [{self.enabled_list}]", Color.White, ColorLog.Level.DEBUG)
        for dev_name, enabled_device in self.enabled_list:
            color_log.log(f"dev_name = {dev_name}, device = {enabled_device}", Color.White, ColorLog.Level.DEBUG)
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
        color_log = ColorLog()

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
                color_log.log(f"Wrong device matching to HA = [{device}]", Color.Red, ColorLog.Level.DEBUG)
                return

        color_log.log(f"Trying to send states to HA : d=[{device}], v=[{value}]", Color.Magenta, ColorLog.Level.DEBUG)

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
                    else:
                        topic = self.make_topic_string(prefix, ha_device, room, PAYLOAD_STATE)
                else:
                    topic = None

            if topic is not None:
                self.mqtt_client.publish(topic, v_value)
                color_log.log(f"[To HA]{topic} = {v_value}", Color.White, ColorLog.Level.DEBUG)
        else:
            color_log.log("MQTT handle is invalid!", Color.Red, ColorLog.Level.CRITICAL)

    def change_aircon_status(self, dev_str: str, room_str: str, aircon_info: Aircon.Info):
        color_log = ColorLog()
        if aircon_info.action in [PAYLOAD_OFF, PAYLOAD_LOCKOFF]:
            mode = PAYLOAD_OFF
        else:
            mode = aircon_info.opmode
        color_log.log(
            f"current action = {aircon_info.action}, opmode = {aircon_info.opmode} => opmode=[{mode}]",
            Color.White,
            ColorLog.Level.DEBUG
        )
        if aircon_info.fanmove == PAYLOAD_SWING:
            swing = PAYLOAD_ON
        else:
            swing = PAYLOAD_OFF
        value = {
            f'{MQTT_MODE}': f'{mode}',
            f'{MQTT_SWING_MODE}': f'{swing}',
            f'{MQTT_FAN_MODE}': f'{aircon_info.fanmode}',
            f'{MQTT_CURRENT_TEMP}': f'{aircon_info.cur_temp:.2f}',
            f'{MQTT_TARGET_TEMP}': f'{aircon_info.target_temp}'
        }
        color_log.log(f"new aircon status = [{value}]", Color.White, ColorLog.Level.DEBUG)
        self.send_state_to_homeassistant(dev_str, room_str, value)

    def on_publish(self, client, obj, mid):
        color_log = ColorLog()
        color_log.log(f"Publish: {str(mid)}", Color.Blue)

    def on_subscribe(self, client, obj, mid, granted_qos):
        color_log = ColorLog()
        color_log.log(f"Subscribed: {str(mid)} {str(granted_qos)}", Color.Blue, ColorLog.Level.DEBUG)

    def on_connect(self, client, userdata, flags, rc):
        color_log = ColorLog()
        if int(rc) == 0:
            color_log.log("[MQTT] connected OK", Color.Yellow)
            self.start_discovery = True
            return
        elif int(rc) == 1:
            color_log.log("[MQTT] 1: Connection refused – incorrect protocol version", Color.Red)
        elif int(rc) == 2:
            color_log.log("[MQTT] 2: Connection refused – invalid client identifier", Color.Red)
        elif int(rc) == 3:
            color_log.log("[MQTT] 3: Connection refused – server unavailable", Color.Red)
        elif int(rc) == 4:
            color_log.log("[MQTT] 4: Connection refused – bad username or password", Color.Red)
        elif int(rc) == 5:
            color_log.log("[MQTT] 5: Connection refused – not authorised", Color.Red)
        else:
            color_log.log(f"[MQTT] {rc} : Connection refused", Color.Red)
        self.mqtt_connect_error = True

    # handle message form homeassistant through mqtt
    def on_message(self, client, obj, msg: pahomqtt.MQTTMessage):
        if not self.ignore_handling:
            rcv_topic = msg.topic.split('/')
            rcv_payload = msg.payload.decode()

            color_log = ColorLog()
            if (
                'config' in rcv_topic
                and (rcv_topic[0], rcv_topic[1], rcv_topic[2])
                    == (cfg.HA_CALLBACK_MAIN, cfg.HA_CALLBACK_BRIDGE, 'config')
            ):
                if rcv_topic[3] == 'log_level':
                    if rcv_payload in ['info', 'debug', 'warn']:
                        color_log.set_level(rcv_payload)
                    color_log.log(f"[From HA]Set Loglevel to {rcv_payload}", Color.Cyan)
                    return
                elif rcv_topic[3] == 'restart':
                    self.homeassistant_device_discovery()
                    color_log.log("[From HA]HomeAssistant Restart", Color.Cyan)
                    return
                elif rcv_topic[3] == 'remove':
                    self.homeassistant_device_discovery(remove=True)
                    color_log.log("[From HA]HomeAssistant Remove", Color.Cyan)
                    return
                elif rcv_topic[3] == 'reconnect':
                    self.reconnect_action()
                    color_log.log("[From HA]Reconnect EW11(s) Called!", Color.Blue)
                    return
                elif rcv_topic[3] == 'check_alive':
                    color_log.log("[From HA]Handler(hacollector) is alive!", Color.Blue)
                    return
            elif not self.start_discovery:
                self.handle_message_from_mqtt(rcv_topic, rcv_payload)
                return
            color_log.log(f"Message: {msg.topic} = {rcv_payload}", Color.White, ColorLog.Level.DEBUG)

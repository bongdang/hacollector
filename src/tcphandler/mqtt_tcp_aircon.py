import asyncio
import json
import time
from typing import Callable

import paho.mqtt.client as pahomqtt # type: ignore

import config as cfg
from loguru import logger
from consts import (DEVICE_AIRCON, DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS,
                    DEVICE_LIGHT, DEVICE_PLUG, DEVICE_SENSOR,
                    DEVICE_THERMOSTAT, MQTT_CURRENT_TEMP, MQTT_FAN_MODE,
                    MQTT_KEEP_ALIVE_SEC, MQTT_MODE, MQTT_SWING_MODE,
                    MQTT_TARGET_TEMP, PAYLOAD_LOCKOFF, PAYLOAD_OFF, PAYLOAD_ON,
                    PAYLOAD_SWING, RS485COMMAND, RS485STAT, RS485TCP)
from tcphandler.appconf_tcphandler import MainConfig
from tcphandler.lgac485_tcp import Aircon, LGACPacketHandler


class AirconHandlerTroughMqtt:
    def __init__(self, config: MainConfig, packet_handler: LGACPacketHandler) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
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
        self.last_publishing_topic: str             = ""
        self.last_publishing_time                   = time.monotonic()
        self.interval                               = 0.1
        self.packet_handler                         = packet_handler
        self.packet_handler.set_notify_as_mqtt_aircon(self.send_mqtt2tcp_aircon_status)

    def set_tcp_send_handler(self, handle_tcp_send_message):
        self.tcp_send_handler: Callable[[str, str, str], None] = handle_tcp_send_message

    def set_reconnect_action(self, reconnect_action):
        self.reconnect_action: Callable[[], None] = reconnect_action

    def set_ignore_handling(self):
        self.ignore_handling = True

    def set_mqtt_client_force(self, mqtt_client):
        self.mqtt_client = mqtt_client

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

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
            username = self.id
            password = self.pw
            self.mqtt_client.username_pw_set(username=username, password=password)
            logger.info(f"{cfg.CONF_MQTT} Configuration: [{server}:{port}] (authenticated)")
        else:
            if not is_anonymous and (self.id == '' or self.pw == ''):
                logger.info(f"{cfg.CONF_MQTT} Credentials missing, falling back to anonymous connection")
            logger.info(f"{cfg.CONF_MQTT} Configuration: [{server}:{port}] (anonymous)")

        logger.info("Connectting MQTT...")
        self.mqtt_client.connect(server, port, MQTT_KEEP_ALIVE_SEC)
        self.mqtt_client.loop_start()
        self.initialize_tcp_topics()

    def cleanup(self) -> None:
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.mqtt_connect_error = True

    def initialize_tcp_topics(self):
        self.subscribe_list = []
#        self.subscribe_list.append((f'{RS485TCP}/#', 0))
        self.publish_list = []

        logger.info("** Starting RS485 mqtt topics.")

        tcp485_list = [
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

        if self.start_discovery:
            self.start_discovery = False

    async def handle_message_from_mqtt_async(self, topic: list[str], payload: str) -> None:
        logger.info(f"<<< From MQTTAIRCON ## topic = [{topic}], payload[{payload}]")
        if type(topic) is not list or len(topic) != 4:
            logger.info("<<< is not Valid topic fot mqtt2tcp_aircon")
        (header, device, command, room) = topic
        if header != RS485TCP:
            logger.info(f"<<< header[{header}] is not Valid topic for mqtt2tcp")
        if device not in [DEVICE_LIGHT, DEVICE_THERMOSTAT,
                          DEVICE_PLUG, DEVICE_GAS, DEVICE_ELEVATOR,
                          DEVICE_FAN, DEVICE_AIRCON, DEVICE_SENSOR]:
            logger.info(f"<<< Unknown Device[{device}]fot mqtt2tcp")

        if command == RS485STAT:
            logger.info(f"<<< STATUS from [{device}] with [{room}]")
        elif command == RS485COMMAND:
            logger.info(f"<<< COMMAND for Aircon[{device}] with [{room}]")
            if device != DEVICE_AIRCON:
                logger.info("This module is for aircon!")
            elif device == DEVICE_AIRCON:
                await self.packet_handler.aircon_tcp_send_handler_async(room, payload)
        else:
            logger.info(f"<<< Unknown command [{command}], [{room}]")

    def handle_message_from_mqtt(self, topic: list[str], payload: str) -> None:
        # Called from paho-mqtt callback thread — must not use asyncio directly.
        # Use run_coroutine_threadsafe to submit to the main event loop safely.
        if self._loop is None:
            logger.warning("Event loop not ready, dropping aircon MQTT message")
            return
        asyncio.run_coroutine_threadsafe(
            self.handle_message_from_mqtt_async(topic, payload), self._loop
        )

    def _build_aircon_state_payload(self, aircon_info: Aircon.Info, fallback_on: bool = False) -> dict:
        if aircon_info.action in [PAYLOAD_OFF, PAYLOAD_LOCKOFF]:
            mode = PAYLOAD_OFF
        else:
            mode = (aircon_info.opmode if aircon_info.opmode != '' else PAYLOAD_ON) if fallback_on else aircon_info.opmode
        swing = PAYLOAD_ON if aircon_info.fanmove == PAYLOAD_SWING else PAYLOAD_OFF
        return {
            f'{MQTT_MODE}': f'{mode}',
            f'{MQTT_SWING_MODE}': f'{swing}',
            f'{MQTT_FAN_MODE}': f'{aircon_info.fanmode}',
            f'{MQTT_CURRENT_TEMP}': f'{int(aircon_info.cur_temp)}',
            f'{MQTT_TARGET_TEMP}': f'{aircon_info.target_temp}'
        }

    def change_aircon_status(self, dev_str: str, room: str, aircon_info: Aircon.Info):
        value = self._build_aircon_state_payload(aircon_info)
        logger.debug(f"current action = {aircon_info.action}, opmode = {aircon_info.opmode} => opmode=[{value[MQTT_MODE]}]")
        logger.info(f">>> room [{room}]------------ ")
        topic_str = f'{RS485TCP}/{DEVICE_AIRCON}/{RS485STAT}/{room}'
        logger.info(f"new aircon status = [{value}]")
        msg_str = json.dumps(value)
        logger.info(f">>> Aircon states to TCP2MQTT_AIRCON t={topic_str}, v=[{msg_str}]")
        if self.mqtt_client is not None:
            last_access_time = time.monotonic()
            if topic_str == self.last_publishing_topic:
                if last_access_time < self.last_publishing_time + self.interval:
                    logger.info(f"SAME topic({topic_str}). so, Ignored!")
                    return
            _ = self.mqtt_client.publish(topic_str, msg_str)
            # color_log.log(f"pub Result : {ret}", Color.Yellow, ColorLog.Level.INFO)
            self.last_publishing_topic = topic_str
            self.last_publishing_time = last_access_time

    def on_publish(self, client, obj, mid):
        logger.info(f"Publish: {str(mid)}")

    def on_subscribe(self, client, obj, mid, granted_qos):
        logger.info(f"[MQTT] Successfully subscribed: {str(mid)} QoS={str(granted_qos)}")

    def on_connect(self, client, userdata, flags, rc):
        if int(rc) == 0:
            logger.info("[MQTT] connected OK")
            self.start_discovery = True
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

    def on_message(self, client, obj, msg: pahomqtt.MQTTMessage):
        if not self.ignore_handling:
            rcv_topic = msg.topic.split('/')
            rcv_payload = msg.payload.decode()

            logger.info(f"[MQTT RECEIVED] Message: {msg.topic} = {rcv_payload}")
            self.handle_message_from_mqtt(rcv_topic, rcv_payload)

    def send_mqtt2tcp_aircon_command(self, room, aircon_info):
        logger.info(f"MQTT2TCP_AIRCON: {room},{aircon_info.opmode},{aircon_info.action}")
        if self.mqtt_client:
            topic = f'{RS485TCP}/aircon/{RS485COMMAND}/{room}'
            value = self._build_aircon_state_payload(aircon_info, fallback_on=True)
            logger.info(f"current action = {aircon_info.action}, opmode = {aircon_info.opmode} => opmode=[{value[MQTT_MODE]}]")
            logger.info(f"new aircon status = [{value}]")
            payload = json.dumps(value)
            self.mqtt_client.publish(topic, payload)
            self.change_aircon_status(DEVICE_AIRCON, room, aircon_info)
        else:
            logger.critical("MQTT handle is invalid!")

    def send_mqtt2tcp_aircon_status(self, dev_str: str, room_str: str, aircon_info: Aircon.Info):
        value = self._build_aircon_state_payload(aircon_info)
        logger.info(f"current action = {aircon_info.action}, opmode = {aircon_info.opmode} => opmode=[{value[MQTT_MODE]}]")
        logger.info(f"new aircon status = [{value}]")

        if self.mqtt_client:
            v_value = json.dumps(value)

            if len(room_str) != 0:
                topic = f'{RS485TCP}/{DEVICE_AIRCON}/{RS485STAT}/{room_str}'
            else:
                topic = None

            if topic is not None:
                self.mqtt_client.publish(topic, v_value)
                logger.info(f"[To HA]{topic} = {v_value}")
        else:
            logger.critical("MQTT handle is invalid!")

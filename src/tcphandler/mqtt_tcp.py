import json
import time
from typing import Callable

import paho.mqtt.client as pahomqtt

import config as cfg
from loguru import logger
from consts import (DEVICE_AIRCON, DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS,
                    DEVICE_LIGHT, DEVICE_PLUG, DEVICE_SENSOR,
                    DEVICE_THERMOSTAT, MQTT_KEEP_ALIVE_SEC, RS485CHECK,
                    RS485COMMAND, RS485STAT, RS485TCP, Command)
from tcphandler.appconf_tcphandler import MainConfig


class MqttTcpHandler:
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
        self.last_publishing_topic: str             = ""
        self.last_publishing_time                   = time.monotonic()
        self.interval                               = 0.1

    def set_tcp_send_handler(self, tcp_send_handler):
        self.tcp_send_handler: Callable[[str, str, str, Command], None] = tcp_send_handler

    def set_reconnect_action(self, reconnect_action):
        self.reconnect_action: Callable[[], None] = reconnect_action

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
            f"{RS485TCP}/{DEVICE_LIGHT}",
            f"{RS485TCP}/{DEVICE_THERMOSTAT}",
            f"{RS485TCP}/{DEVICE_PLUG}",
            f"{RS485TCP}/{DEVICE_FAN}",
            f"{RS485TCP}/{DEVICE_GAS}",
            f"{RS485TCP}/{DEVICE_ELEVATOR}",
            f"{RS485TCP}/{DEVICE_SENSOR}",
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

    def handle_message_from_mqtt(self, topic: list[str], payload: str) -> None:
        logger.debug(f"<<< From MQTT ## topic = [{topic}], payload[{payload}]")
        if type(topic) is not list or len(topic) != 4:
            logger.debug("<<< is not Valid topic fot mqtt2tcp")
        (header, device, command, room) = topic
        if header != RS485TCP:
            logger.debug(f"<<< header[{header}] is not Valid topic for mqtt2tcp")
        if device not in [DEVICE_LIGHT, DEVICE_THERMOSTAT,
                          DEVICE_PLUG, DEVICE_GAS, DEVICE_ELEVATOR, 
                          DEVICE_FAN, DEVICE_AIRCON, DEVICE_SENSOR]:
            logger.debug(f"<<< Unknown Device[{device}]fot mqtt2tcp")

        if command == RS485STAT:
            logger.debug(f"<<< STATUS from [{device}] with [{room}]")
        elif command == RS485COMMAND:
            logger.debug(f"<<< COMMAND for [{device}] with [{room}]")
            if device != DEVICE_AIRCON:
                self.tcp_send_handler(device, room, payload, Command.STATUS)
            elif device == DEVICE_AIRCON:
                logger.info("Aircon Handler is not in this module!!")
        elif command == RS485CHECK:
            logger.debug(f"<<< CHECK status for [{device}] with [{room}]")
            if device != DEVICE_AIRCON:
                self.tcp_send_handler(device, room, payload, Command.CHECK)
            elif device == DEVICE_AIRCON:
                logger.info("Aircon Handler is not in this module!!")
        else:
            logger.debug(f"<<< Unknown command [{command}], [{room}]")

    def send_state_to_mqtt(self, device: str, room: str, value: dict) -> None:

        if len(room) == 0:
            room = "0"
        logger.debug(f">>> room [{room}]------------ ")
        topic_str = f'{RS485TCP}/{device}/{RS485STAT}/{room}'
        msg_str = json.dumps(value)
        logger.debug(f">>> Sending states to MQTT : d=[{device}], v=[{value}]")
        if self.mqtt_client is not None:
            last_access_time = time.monotonic()
            if topic_str == self.last_publishing_topic:
                if last_access_time < self.last_publishing_time + self.interval:
                    logger.info(f"SAME topic({topic_str}). so, Ignored!")
                    return
            _ = self.mqtt_client.publish(topic_str, msg_str)
            # color_log.log(f"pub Result : {ret}", Color.Yellow, ColorLog.Level.DEBUG)
            self.last_publishing_topic = topic_str
            self.last_publishing_time = last_access_time

    def on_publish(self, client, obj, mid):
        logger.debug(f"Publish: {str(mid)}")

    def on_subscribe(self, client, obj, mid, granted_qos):
        logger.debug(f"Subscribed: {str(mid)} {str(granted_qos)}")

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

            logger.debug(f"Message: {msg.topic} = {rcv_payload}")
            self.handle_message_from_mqtt(rcv_topic, rcv_payload)

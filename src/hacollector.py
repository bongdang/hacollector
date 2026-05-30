import asyncio
import configparser
import os
import pathlib
import sys
import time

from dotenv import load_dotenv
from loguru import logger

import config as cfg
from tcphandler.appconf_tcphandler import MainConfig
from common.utils import setup_logger
from consts import DEVICE_AIRCON, SW_VERSION_STRING
from devices.hub import Hub
from handlers.aircon_handler import GeneralAirconHandler
from handlers.kocom_handler import KocomHandlerMqtt
from handlers.mqtt_handler import MqttHandler


async def main(loop: asyncio.AbstractEventLoop, first_run: bool):
    root_dir = pathlib.Path.cwd()
    conf_candidates = [root_dir / cfg.CONF_FILE, pathlib.Path('/hacollector') / cfg.CONF_FILE]
    env_candidates = [root_dir / '.env', pathlib.Path('/hacollector/.env')]

    if first_run:
        log_dir_env = os.environ.get('LOG_DIR', '')
        log_root = pathlib.Path(log_dir_env) if log_dir_env else root_dir
        log_sub = '' if log_dir_env else 'log'
        log_dir = log_root if not log_sub else log_root / log_sub
        if not setup_logger('hacollector', log_dir=log_dir, file_name=cfg.CONF_LOGFILE, level=cfg.CONF_LOGLEVEL, emit_banner=False):
            sys.exit(1)

    logger.info(f"Starting...{SW_VERSION_STRING}")

    config = configparser.ConfigParser()
    app_config = MainConfig()
    conf_path = next((path for path in conf_candidates if path.exists()), None)
    if conf_path is not None:
        config.read(conf_path)
        if not app_config.read_config_file(config):
            logger.warning("hacollector configuration file is invalid. Falling back to environment values.")

    env_path = next((path for path in env_candidates if path.exists()), None)
    if env_path is not None:
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
    app_config.load_env_values()

    # Re-configure logger level now that config is loaded.
    log_dir_env = os.environ.get('LOG_DIR', '')
    log_root = pathlib.Path(log_dir_env) if log_dir_env else root_dir
    log_sub = '' if log_dir_env else 'log'
    log_dir = log_root if not log_sub else log_root / log_sub
    setup_logger('hacollector', log_dir=log_dir, file_name=cfg.CONF_LOGFILE, level=app_config.log_level)

    if not app_config.has_mqtt_config():
        logger.error("MQTT configuration is missing!")
        sys.exit(1)
    if not app_config.has_kocom_config():
        logger.error("Kocom configuration is missing!")
        sys.exit(1)
    if not app_config.has_aircon_config():
        logger.error("Aircon configuration is missing!")
        sys.exit(1)

    kocom = KocomHandlerMqtt(app_config)
    aircon = GeneralAirconHandler(app_config)
    mqtt = MqttHandler(app_config)

    def prepare_reconnect():
        mqtt.set_ignore_handling()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    logger.info(f"{cfg.CONF_KOCOM_DEVICE_NAME} Configuration: [{app_config.kocom_server}:{app_config.kocom_port}]")
    logger.info(f"{cfg.CONF_AIRCON_DEVICE_NAME} Configuration: [{app_config.aircon_server}:{app_config.aircon_port}]")

    # setup callback functions
    # notify function kocom -> homeassistant
    kocom.wallpad.set_notify_to_homeassistant(mqtt.send_state_to_homeassistant)
    aircon.mqtt_aircon_handler.packet_handler.set_notify_to_homeassistant_aircon(mqtt.send_aircon_state_to_homeassistant)
    # notify function homeassistant -> kocom
    mqtt.set_kocom_mqtt_handler(kocom.wallpad.handle_kocom_mqtt_message)
    # notify function aircon -> kocom
    mqtt.set_aircon_mqtt_handler(aircon.handle_aircon_mqtt_message)
    # reconnection assist function
    mqtt.set_reconnect_action(prepare_reconnect)

    # handler function homeassistant -> kocom
    mqtt.set_kocom_tcp2mqtt_handler(kocom.kocom_tcp2mqtt_handler)
    # handler function made mqtt messge from aircon mqtt.
    mqtt.set_handle_mqtt_from_tcp_aircon(aircon.notify_to_ha_from_aircon_made_mqtt)
    # handler function in wallpad homeassistant -> each device
    kocom.wallpad.set_send_mqtt2tcp_command(mqtt.send_mqtt2tcp_command)
    # aircon handler function in homeassistant -> each device

    # setup hub = device manager
    hub = Hub(mqtt, kocom.wallpad)

    if hub is not None:
        # add each rs485 devices from config file
        hub.add_devices(kocom.enabled_dev)
        hub.add_devices([DEVICE_AIRCON])
        enabled_list = []
        enabled_list.extend(kocom.wallpad.enabled_device_list)
        enabled_list.extend(aircon.enabled_device_list)
        mqtt.set_enabled_list(enabled_list)

        logger.debug("Now entering main loop!")

        # verify all required callbacks are wired before connecting
        _required = ['kocom_mqtt_handler', 'aircon_mqtt_handler',
                     'kocom_tcp_handler', 'handle_mqtt_from_tcp_aircon', 'reconnect_action']
        _missing = [cb for cb in _required if not hasattr(mqtt, cb)]
        if _missing:
            logger.critical(f"Missing MQTT callbacks: {_missing}")
            sys.exit(1)

        try:
            mqtt.connect_mqtt()
            aircon.mqtt_aircon_handler.set_mqtt_client_force(mqtt.mqtt_client)

        except Exception as e:
            logger.critical(f"Error connecting Servers. Check MQTT or EW11 configuration!({e})")
            sys.exit(1)

        tasks = asyncio.gather(
            hub.async_scan_thread()
        )
        try:
            await tasks
        except asyncio.CancelledError:
            logger.info("Restart revoked by HomeAssistant Web Service.")
            pass
        logger.debug("========= END loop(Will not show!) ========")
    else:
        logger.critical("[ERROR] Something is wrong. check configuration!")

    logger.info("End of Program.")
    loop.stop()

# main
if __name__ == '__main__':
    loop: asyncio.AbstractEventLoop
    first_run: bool = True
    while True:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(main(loop, first_run))
            loop.close()
            first_run = False
            logger.info("Exit from main loop. Restarting!")
        except KeyboardInterrupt:
            print("User send Ctrl-C. so, Exiting...")
            sys.exit(1)
        time.sleep(3)
        print("* Maybe Called by HA for reconnect EW11 devices. so, Restarting.*")

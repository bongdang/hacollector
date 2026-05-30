import argparse
import asyncio
import configparser
import os
import pathlib
import sys
import time

from dotenv import load_dotenv
from loguru import logger

import config as cfg
from common.utils import setup_logger
from tcphandler.appconf_tcphandler import MainConfig
from handlers.aircon_handler import GeneralAirconHandler
# from tcphandler.mqtt_tcp_aircon import AirconHandlerTroughMqtt

# from consts import (DEVICE_LIGHT, DEVICE_THERMOSTAT,
#                     DEVICE_PLUG, DEVICE_GAS, DEVICE_ELEVATOR,
#                     DEVICE_FAN, DEVICE_AIRCON, DEVICE_SENSOR)


async def main():
    root_dir = pathlib.Path.cwd()
    conf_candidates = [root_dir / cfg.CONF_FILE, pathlib.Path('/hacollector') / cfg.CONF_FILE]
    env_candidates = [root_dir / '.env', pathlib.Path('/hacollector/.env')]

    parser = argparse.ArgumentParser(description="how to use in command line cls_lgac485.py")

    parser.add_argument("--publish", "-p", help="Publish to MQTT", type=bool)
    parser.add_argument('--verbose', '-v', help="Print detail information")

    args = parser.parse_args()

    log_dir_env = os.environ.get('LOG_DIR', '')
    log_root = pathlib.Path(log_dir_env) if log_dir_env else root_dir
    log_sub = '' if log_dir_env else 'log'
    log_dir = log_root if not log_sub else log_root / log_sub
    if not setup_logger('tcp2mqtt_aircon', log_dir=log_dir, file_name='tcp2mqtt_aircon.log', level='info', emit_banner=False):
        sys.exit(1)

    config = configparser.ConfigParser()
    app_config = MainConfig()
    conf_path = next((path for path in conf_candidates if path.exists()), None)
    if conf_path is not None:
        config.read(conf_path)
        if not app_config.read_config_file(config):
            logger.warning("tcp2mqtt_aircon configuration file is invalid. Falling back to environment values!")

    env_path = next((path for path in env_candidates if path.exists()), None)
    if env_path is not None:
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
    app_config.load_env_values()
    setup_logger('tcp2mqtt_aircon', log_dir=log_dir, file_name='tcp2mqtt_aircon.log', level=app_config.log_level)

    if not app_config.has_mqtt_config():
        logger.error("MQTT configuration is missing!")
        sys.exit(1)
    if not app_config.has_aircon_config():
        logger.error("Aircon configuration is missing!")
        sys.exit(1)

    print(args)
    if args.publish:
        print("Data Will be Published.")

    aircon_handler = GeneralAirconHandler(app_config, True)
    aircon_handler.mqtt_aircon_handler.set_event_loop(asyncio.get_running_loop())

    try:
        tasks = asyncio.gather(
            aircon_handler.mqtt_aircon_handler.packet_handler.async_scan_aircons_loop(),
        )
        try:
            await tasks
        except asyncio.CancelledError:
            logger.info("Some not handled msg. so, Exiting..")
            pass
    finally:
        try:
            aircon_handler.mqtt_aircon_handler.cleanup()
        except Exception as e:
            logger.error(f"Aircon MQTT cleanup error: {e}")

    return


if __name__ == '__main__':
    while True:
        try:
            asyncio.run(main())
            logger.info("Exit from aircon main loop. Restarting!")
        except KeyboardInterrupt:
            print("User send Ctrl-C. so, Exiting...")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unhandled exception in tcp2mqtt_aircon: {e}")
        time.sleep(3)
        print("* Restarting tcp2mqtt_aircon loop *")

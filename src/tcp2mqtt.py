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
from tcphandler.kocom_tcp import KocomHandler
from tcphandler.mqtt_tcp import MqttTcpHandler


class FakeHub():
    def __init__(self, kocom_handler) -> None:
        self.kocom_handler: KocomHandler        = kocom_handler

    async def async_scan_thread(self) -> None:
        while True:
            await asyncio.sleep(0.5 * 2)


async def main(loop: asyncio.AbstractEventLoop, first_run: bool):
    root_dir = pathlib.Path.cwd()
    conf_candidates = [root_dir / cfg.CONF_FILE, pathlib.Path('/hacollector') / cfg.CONF_FILE]
    env_candidates = [root_dir / '.env', pathlib.Path('/hacollector/.env')]

    log_dir_env = os.environ.get('LOG_DIR', '')
    log_root = pathlib.Path(log_dir_env) if log_dir_env else root_dir
    log_sub = '' if log_dir_env else 'log'
    log_dir = log_root if not log_sub else log_root / log_sub
    if first_run:
        if not setup_logger('tcp2mqtt', log_dir=log_dir, file_name='tcp2mqtt.log', level='info', emit_banner=False):
            sys.exit(1)

    parser = argparse.ArgumentParser(description="how to use in command line cls_lgac485.py")

    parser.add_argument("--publish", "-p", help="Publish to MQTT", type=bool)
    parser.add_argument('--verbose', '-v', help="Print detail information")

    args = parser.parse_args()

    config = configparser.ConfigParser()
    app_config = MainConfig()
    conf_path = next((path for path in conf_candidates if path.exists()), None)
    if conf_path is not None:
        config.read(conf_path)
        if not app_config.read_config_file(config):
            logger.warning("tcp2mqtt configuration file is invalid. Falling back to environment values.")

    env_path = next((path for path in env_candidates if path.exists()), None)
    if env_path is not None:
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
    app_config.load_env_values()
    # Re-init after env load so app_config.log_level (stderr) and FILE_LOGLEVEL (file sink)
    # take effect — mirrors tcp2mqtt_aircon.py / hacollector.py.
    setup_logger('tcp2mqtt', log_dir=log_dir, file_name='tcp2mqtt.log', level=app_config.log_level)

    if not app_config.has_mqtt_config():
        logger.error("MQTT configuration is missing!")
        sys.exit(1)
    if not app_config.has_kocom_config():
        logger.error("Kocom configuration is missing!")
        sys.exit(1)

    print(args)
    if args.publish:
        print("Data Will be Published.")

    kocom_handler = KocomHandler(app_config)
    mqtt_handler = MqttTcpHandler(app_config)
    kocom_handler.set_mqtt_handler(mqtt_handler.send_state_to_mqtt)

    def close_all_devices_sockets():
        kocom_handler.sync_close_socket(loop)

    def prepare_reconnect():
        mqtt_handler.set_ignore_handling()
        close_all_devices_sockets()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    mqtt_handler.set_tcp_send_handler(kocom_handler.tcp_send_handler)

    mqtt_handler.set_reconnect_action(prepare_reconnect)

    mqtt_handler.connect_mqtt()

    try:
        await kocom_handler.async_prepare_communication()
        tasks = asyncio.gather(
            kocom_handler.kocom_main_read_loop(),
        )
        try:
            await tasks
        except asyncio.CancelledError:
            logger.info("Restart revoked by HomeAssistant Web Service.")
            pass
    finally:
        try:
            mqtt_handler.cleanup()
        except Exception as e:
            logger.error(f"MQTT cleanup error: {e}")
        try:
            await kocom_handler.comm.close_async_socket()
        except Exception as e:
            logger.error(f"Kocom socket close error: {e}")

    return


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

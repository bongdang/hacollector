import asyncio
import configparser
import pathlib
import sys

from dotenv import load_dotenv

import config as cfg
from classes.appconf import MainConfig
from classes.hub import Hub
from classes.kocom import KocomHandler
from classes.lgac485 import LGACPacketHandler
from classes.mqtt import MqttHandler
from classes.utils import Color, ColorLog
from consts import DEVICE_AIRCON, SW_VERSION_STRING


async def main(loop: asyncio.AbstractEventLoop, first_run: bool):
    root_dir = pathlib.Path.cwd()

    color_log: ColorLog

    if first_run:
        color_log = ColorLog(cfg.CONF_LOGFILE)
        if not color_log.prepare_logs(root=root_dir, sub_path='log', file_name=cfg.CONF_LOGFILE):
            sys.exit(1)
        color_log.set_level(cfg.CONF_LOGLEVEL)
    else:
        color_log = ColorLog()

    color_log.log(f"Starting...{SW_VERSION_STRING}", Color.Yellow)

    conf_path = root_dir / cfg.CONF_FILE

    config = configparser.ConfigParser()
    config.read(conf_path)

    app_config = MainConfig()
    if not app_config.read_config_file(config):
        color_log.log("haclooector Configuration is invalid!", Color.Red)
        sys.exit(1)

    load_dotenv()
    app_config.load_env_values()
    color_log.set_level(app_config.log_level)

    kocom = KocomHandler(app_config)
    aircon = LGACPacketHandler(app_config)
    mqtt = MqttHandler(app_config)

    def close_all_devices_sockets():
        kocom.sync_close_socket(loop)
        aircon.sync_close_socket(loop)

    def prepare_reconnect():
        mqtt.set_ignore_handling()
        close_all_devices_sockets()
        for task in asyncio.all_tasks(loop):
            task.cancel()

    color_log.log(f"{cfg.CONF_KOCOM_DEVICE_NAME} Configuration: [{app_config.kocom_server}:{app_config.kocom_port}]")
    color_log.log(f"{cfg.CONF_AIRCON_DEVICE_NAME} Configuration: [{app_config.aircon_server}:{app_config.aircon_port}]")

    # setup callback functions
    kocom.wallpad.set_notify_function(mqtt.send_state_to_homeassistant)
    aircon.set_notify_function(mqtt.change_aircon_status)
    mqtt.set_kocom_mqtt_handler(kocom.wallpad.handle_wallpad_mqtt_message)
    mqtt.set_aircon_mqtt_handler(aircon.handle_aircon_mqtt_message)
    mqtt.set_reconnect_action(prepare_reconnect)

    hub = Hub(kocom, aircon, mqtt, kocom.wallpad)

    # add each rs485 devices
    hub.add_devices(kocom.enabled_dev)
    hub.add_devices([DEVICE_AIRCON])
    enabled_list = []
    enabled_list.extend(kocom.wallpad.enabled_device_list)
    enabled_list.extend(aircon.enabled_device_list)
    mqtt.set_enabled_list(enabled_list)

    if hub is not None:
        color_log.log("Now entering main loop!", Color.Green, ColorLog.Level.DEBUG)

        try:
            mqtt.connect_mqtt()
            await hub.kocom_handler.async_prepare_communication()
        except Exception as e:
            color_log.log(
                f"Error connecting Servers. Check MQTT or EW11 configuration!({e})",
                Color.Red,
                ColorLog.Level.CRITICAL
            )
            sys.exit(1)

        tasks = asyncio.gather(
            hub.kocom_handler.kocom_main_read_loop(),
            hub.kocom_handler.kocom_main_write_loop(),
            aircon.async_lgac_main_write_loop(),
            hub.async_scan_thread()
        )
        try:
            await tasks
        except asyncio.CancelledError:
            color_log.log("Restart revoked by HomeAssistant Web Service.")
            pass
        color_log.log("========= END loop(Will not show!) ========", Color.Red, ColorLog.Level.DEBUG)
    else:
        color_log.log("[ERROR] Something is wrong. check configuration!", Color.Red, ColorLog.Level.CRITICAL)

    color_log.log("End of Program.")
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
            color_log = ColorLog()
            color_log.log("Exit from main loop. Restarting!", Color.Blue)
        except KeyboardInterrupt:
            print("User send Ctrl-C. so, Exiting...")
            sys.exit(1)
        print("* Maybe Called by HA for reconnect EW11 devices. so, Restarting.*")

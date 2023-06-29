# Default socker buffer size
MAX_SOCKET_BUFFER   = 2048

# Default Log Level
CONF_LOGLEVEL       = 'info'          # debug, info, warn

# HA MQTT Discovery
HA_PREFIX           = 'homeassistant'
HA_SWITCH           = 'switch'
HA_LIGHT            = 'light'
HA_CLIMATE          = 'climate'
HA_SENSOR           = 'sensor'
HA_FAN              = 'fan'
HA_GAS              = 'gas'
HA_CALLBACK_MAIN    = 'rs485'
HA_CALLBACK_BRIDGE  = 'bridge'


CONF_FILE               = 'hacollector.conf'
CONF_LOGFILE            = 'hacollector.log'
CONF_LOGNAME            = 'hacollector'
CONF_KOCOM_DEVICE_NAME  = 'kocom'
CONF_AIRCON_DEVICE_NAME = 'LGAircon'
CONF_RS485_DEVICES      = 'RS485Devices'
CONF_MQTT               = 'MQTT'
CONF_ADVANCED           = 'advanced'

INIT_TEMP = 22

KOCOM_PLUG_SIZE = {
    'livingroom': 2,
    'bedroom': 2,
    'room1': 2,
    'room2': 2,
    'room3': 2,
    'kitchen': 2
}
KOCOM_LIGHT_SIZE = {
    'livingroom': 3
}

# room1 = 1ST,room2 = 2ND,room3 = READING
KOCOM_ROOM = {
    '00': 'livingroom',
    '01': 'bedroom',
    '02': 'room2',
    '03': 'room1',
    '04': 'room3',
    '05': 'kitchen'
}
KOCOM_ROOM_THERMOSTAT = {
    '00': 'livingroom',
    '01': 'bedroom',
    '02': 'room1',
    '03': 'room2',
    '04': 'room3'
}
SYSTEM_ROOM_AIRCON = {
    '00': 'livingroom',
    '01': 'kitchen',
    '02': 'bedroom',
    '03': 'room2',
    '04': 'room1',
    '05': 'room3'
}

WALLPAD_SCAN_INTERVAL_TIME  = 120.
PACKET_RESEND_INTERVAL_SEC  = 0.8

RS485_WRITE_INTERVAL_SEC    = 0.1

DEFAULT_SPEED               = 'low'

ALTERNATIVE_HEADER_DEBUG    = False
TEMPERATURE_ADJUST          = 0.5

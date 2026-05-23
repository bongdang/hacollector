import asyncio
import sys
import os

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv # type: ignore

from loguru import logger
from common.utils import setup_logger
from devices.aircon import Aircon
from tcphandler.appconf_tcphandler import MainConfig
from tcphandler.lgac485_tcp import LGACPacket, LGACPacketHandler

# DEPRECATED: 진단 CLI 통합으로 대체되었습니다.
#   기존:  python src/test/lgac_test.py --id 1 --action status
#   신규:  cd src && python -m cli aircon status --id 1
#          cd src && python -m cli aircon set --id 1 --mode cool --temp 25
#          cd src && python -m cli aircon off --id 1
#          cd src && python -m cli aircon decode <hex>
# 이 스크립트는 하위 호환을 위해 유지되며, 다음 사이클에서 제거될 예정입니다.
print(
    "[DEPRECATED] lgac_test.py는 곧 제거됩니다. `python -m cli aircon --help` 사용을 권장합니다.",
    file=sys.stderr,
)


def synchronize_async_helper(to_await):
    return asyncio.run(to_await)


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(description="LGAC Test - Query/Control Air Conditioner status")

    parser.add_argument("--group", "-g", help="group ID (default: 0)", default="0")
    parser.add_argument("--id", "-i", help="aircon ID", required=True)
    parser.add_argument("--action", "-a", help="action (e.g., status, on, off)", default="status")
    parser.add_argument("--operation", "-o", help="operation mode (cool, heat, dry, fan_only, auto)", default="cool")
    parser.add_argument("--fanmove", "-m", help="fan move (swing, fixed)", default="fixed")
    parser.add_argument("--fanmode", "-s", help="fan mode (low, medium, high, auto, silent, power)", default="low")
    parser.add_argument("--temp", "-t", help="temperature setting (18-30)", default="25")
    parser.add_argument('--status', action='store_true', help="Quick status check - shortcut for status query")
    parser.add_argument('--checkchunk', '-c', help="Check One Chunk from hex string")

    args = parser.parse_args()

    setup_logger('lgac_test', level='info')
    app_config = MainConfig()
    load_dotenv()
    app_config.load_env_values()

    if args.checkchunk is not None:

        chunk = LGACPacket()
        instr: str = str(args.checkchunk)
        logger.info(f'input = {instr}')

        chunk.set_packet_data(bytes.fromhex(instr))
        logger.info(f'Result = {chunk}')

        return

    # Use --status flag for convenient status queries
    if args.status:
        args.action = 'status'

    handler = LGACPacketHandler(app_config)
    aircon_cmd = Aircon.Info(args.action, args.operation, args.fanmove, args.fanmode, 25, int(args.temp))
    
    try:
        info: Aircon.Info | None = synchronize_async_helper(handler.async_send_and_get_result(0, int(args.id), aircon_cmd))
    except RuntimeError as e:
        logger.error(f"Communication error: {e}")
        info = None

    if info is not None:
        logger.info(f'action={info.action}, opmode={info.opmode}, fanmove={info.fanmove}, fanmode={info.fanmode}, '
            f'current_temp={info.cur_temp}, set_temp={info.target_temp}, ')
    else:
        logger.warning("Error Return.")

    return


if __name__ == '__main__':
    main(sys.argv)

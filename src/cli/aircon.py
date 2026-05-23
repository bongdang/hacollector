import asyncio

import typer
from loguru import logger

from cli._common import load_app_config
from devices.aircon import Aircon
from tcphandler.lgac485_tcp import LGACPacket, LGACPacketHandler


app = typer.Typer(no_args_is_help=True, add_completion=False)


def _run(coro):
    return asyncio.run(coro)


def _print_info(info: Aircon.Info | None) -> None:
    if info is None:
        logger.warning("Error Return.")
        raise typer.Exit(code=1)
    logger.info(
        f"action={info.action}, opmode={info.opmode}, fanmove={info.fanmove}, "
        f"fanmode={info.fanmode}, current_temp={info.cur_temp}, set_temp={info.target_temp}"
    )


@app.command()
def status(
    aircon_id: int = typer.Option(..., "--id", "-i", help="에어컨 ID"),
    group: int = typer.Option(0, "--group", "-g", help="그룹 ID (기본 0)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """현재 상태 조회 (status 액션)."""
    app_config = load_app_config(verbose=verbose)
    handler = LGACPacketHandler(app_config)
    cmd = Aircon.Info("status", "cool", "fixed", "low", 25, 25)
    try:
        info = _run(handler.async_send_and_get_result(group, aircon_id, cmd))
    except RuntimeError as e:
        logger.error(f"Communication error: {e}")
        raise typer.Exit(code=1)
    _print_info(info)


@app.command()
def set(  # noqa: A001 - typer command name
    aircon_id: int = typer.Option(..., "--id", "-i", help="에어컨 ID"),
    group: int = typer.Option(0, "--group", "-g", help="그룹 ID (기본 0)"),
    mode: str = typer.Option("cool", "--mode", "-o", help="운전 모드: cool, heat, dry, fan_only, auto"),
    fan: str = typer.Option("low", "--fan", "-s", help="풍량: low, medium, high, auto, silent, power"),
    swing: str = typer.Option("fixed", "--swing", "-m", help="풍향: swing, fixed"),
    temp: int = typer.Option(25, "--temp", "-t", min=18, max=30, help="설정 온도 (18-30)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """전원 on + 모드/풍량/풍향/온도 설정."""
    app_config = load_app_config(verbose=verbose)
    handler = LGACPacketHandler(app_config)
    cmd = Aircon.Info("on", mode, swing, fan, 25, temp)
    try:
        info = _run(handler.async_send_and_get_result(group, aircon_id, cmd))
    except RuntimeError as e:
        logger.error(f"Communication error: {e}")
        raise typer.Exit(code=1)
    _print_info(info)


@app.command()
def off(
    aircon_id: int = typer.Option(..., "--id", "-i", help="에어컨 ID"),
    group: int = typer.Option(0, "--group", "-g", help="그룹 ID (기본 0)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """전원 off."""
    app_config = load_app_config(verbose=verbose)
    handler = LGACPacketHandler(app_config)
    cmd = Aircon.Info("off", "cool", "fixed", "low", 25, 25)
    try:
        info = _run(handler.async_send_and_get_result(group, aircon_id, cmd))
    except RuntimeError as e:
        logger.error(f"Communication error: {e}")
        raise typer.Exit(code=1)
    _print_info(info)


@app.command()
def decode(
    hex_str: str = typer.Argument(..., help="LGAC 패킷 hex 문자열 (예: a022...)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """원본 hex 패킷을 디코딩해 사람이 읽을 수 있는 필드로 출력."""
    load_app_config(verbose=verbose)
    chunk = LGACPacket()
    logger.info(f"input = {hex_str}")
    try:
        chunk.set_packet_data(bytes.fromhex(hex_str))
    except ValueError as e:
        logger.error(f"Invalid hex string: {e}")
        raise typer.Exit(code=2)
    logger.info(f"Result = {chunk}")

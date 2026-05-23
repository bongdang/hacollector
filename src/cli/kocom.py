import asyncio
import json

import typer
from loguru import logger

from cli._common import load_app_config
from consts import (Command, DEVICE_ELEVATOR, DEVICE_FAN, DEVICE_GAS,
                    DEVICE_LIGHT, DEVICE_PLUG, DEVICE_THERMOSTAT,
                    MQTT_MODE, MQTT_PRESET_MODE, MQTT_TARGET_TEMP,
                    PAYLOAD_FAN_ONLY, PAYLOAD_HEAT, PAYLOAD_HIGH, PAYLOAD_LOW,
                    PAYLOAD_MEDIUM, PAYLOAD_OFF, PAYLOAD_ON)
from tcphandler.kocom_devices import RS485DeviceHandler
from tcphandler.kocom_tcp import KocomHandler, KocomPacket


app = typer.Typer(no_args_is_help=True, add_completion=False)


def _apply_overrides(app_config, server: str | None, port: int | None) -> None:
    if server is not None:
        app_config.kocom_server = server
    if port is not None:
        app_config.kocom_port = str(port)
    if not app_config.kocom_server:
        logger.error("Kocom host not set. Use --server or configure KOCOM_SERVER_IP.")
        raise typer.Exit(code=2)


def _parse_index_list(spec: str) -> set[int]:
    if not spec.strip():
        return set()
    out: set[int] = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.add(int(tok))
        except ValueError:
            logger.error(f"invalid switch index: {tok!r}")
            raise typer.Exit(code=2)
    return out


async def _send(app_config, device_str: str, room_str: str, payload_dict: dict) -> None:
    handler = KocomHandler(app_config)
    await handler.async_prepare_communication()
    try:
        rs485 = RS485DeviceHandler(None, None, None, 0)
        payload_str = json.dumps(payload_dict)
        packet = rs485.make_packet(device_str, payload_str, Command.STATUS, room_str)
        if not packet:
            logger.error(f"failed to build packet (device={device_str}, room={room_str})")
            raise typer.Exit(code=1)
        logger.info(f"sending [{device_str}/{room_str or '-'}] = {payload_dict}")
        logger.debug(f"hex = {packet.hex()}")
        ok = await handler.comm.async_write_one_chunk(packet)
        if not ok:
            logger.error("write failed")
            raise typer.Exit(code=1)
        logger.info("sent")
    finally:
        await handler.comm.close_async_socket()


@app.command()
def decode(
    hex_str: str = typer.Argument(..., help="Kocom 패킷 hex 문자열 (예: 30dc...0d0d)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """원본 hex 패킷을 디코딩해 device/room/payload로 출력."""
    load_app_config(verbose=verbose)
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError as e:
        logger.error(f"invalid hex: {e}")
        raise typer.Exit(code=2)
    packet = KocomPacket(raw)
    try:
        notify, device, room, payload = packet.parse_data_from_packet()
    except Exception as e:
        logger.error(f"parse failed: {e}")
        raise typer.Exit(code=1)
    logger.info(f"device={device or '-'} room={room or '-'} notify={notify} payload={payload}")


def _switch_payload(device_key: str, max_index: int, on_set: set[int]) -> dict:
    out = {}
    for i in range(1, max_index + 1):
        out[f"{device_key}{i}"] = PAYLOAD_ON if i in on_set else PAYLOAD_OFF
    return out


@app.command()
def light(
    room: str = typer.Option(..., "--room", "-r", help="방 이름 (예: livingroom, bedroom, room1)"),
    on: str = typer.Option("", "--on", help="ON으로 설정할 light 번호. 예: '1,3'. 빈 문자열이면 모두 OFF"),
    count: int = typer.Option(3, "--count", "-n", min=1, max=8, help="해당 방의 light 개수"),
    server: str | None = typer.Option(None, "--server", "-s"),
    port: int | None = typer.Option(None, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """방 단위 light 상태 설정 (지정 안 한 번호는 OFF)."""
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, server, port)
    on_set = _parse_index_list(on)
    payload = _switch_payload("light", count, on_set)
    asyncio.run(_send(app_config, DEVICE_LIGHT, room, payload))


@app.command()
def plug(
    room: str = typer.Option(..., "--room", "-r", help="방 이름"),
    on: str = typer.Option("", "--on", help="ON으로 설정할 plug 번호. 예: '1,2'"),
    count: int = typer.Option(2, "--count", "-n", min=1, max=8, help="해당 방의 plug 개수"),
    server: str | None = typer.Option(None, "--server", "-s"),
    port: int | None = typer.Option(None, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """방 단위 plug 상태 설정 (지정 안 한 번호는 OFF)."""
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, server, port)
    on_set = _parse_index_list(on)
    payload = _switch_payload("plug", count, on_set)
    asyncio.run(_send(app_config, DEVICE_PLUG, room, payload))


@app.command()
def thermostat(
    room: str = typer.Option(..., "--room", "-r", help="방 이름"),
    mode: str = typer.Option(..., "--mode", "-m", help="heat | off | fan_only(외출)"),
    target: int = typer.Option(22, "--target", "-t", min=5, max=40, help="목표 온도"),
    server: str | None = typer.Option(None, "--server", "-s"),
    port: int | None = typer.Option(None, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """난방 mode 및 target_temp 설정."""
    allowed = {PAYLOAD_HEAT, PAYLOAD_OFF, PAYLOAD_FAN_ONLY}
    if mode not in allowed:
        logger.error(f"--mode must be one of {sorted(allowed)}, got {mode!r}")
        raise typer.Exit(code=2)
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, server, port)
    payload = {MQTT_MODE: mode, MQTT_TARGET_TEMP: target}
    asyncio.run(_send(app_config, DEVICE_THERMOSTAT, room, payload))


@app.command()
def fan(
    speed: str = typer.Option(..., "--speed", "-s", help="low | medium | high | off"),
    server: str | None = typer.Option(None, "--server"),
    port: int | None = typer.Option(None, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """공기순환기 풍량 설정."""
    allowed = {PAYLOAD_LOW, PAYLOAD_MEDIUM, PAYLOAD_HIGH, PAYLOAD_OFF}
    if speed not in allowed:
        logger.error(f"--speed must be one of {sorted(allowed)}, got {speed!r}")
        raise typer.Exit(code=2)
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, server, port)
    payload = {MQTT_PRESET_MODE: speed}
    asyncio.run(_send(app_config, DEVICE_FAN, "", payload))


@app.command()
def gas(
    off: bool = typer.Option(False, "--off", help="가스밸브 OFF (안전상 OFF만 지원)"),
    server: str | None = typer.Option(None, "--server", "-s"),
    port: int | None = typer.Option(None, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """가스밸브 OFF. ON은 지원하지 않음 (월패드 안전 정책)."""
    if not off:
        logger.error("Specify --off explicitly. Gas ON is not supported.")
        raise typer.Exit(code=2)
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, server, port)
    payload = {DEVICE_GAS: PAYLOAD_OFF}
    asyncio.run(_send(app_config, DEVICE_GAS, "", payload))


@app.command()
def elevator(
    call: bool = typer.Option(False, "--call", help="엘리베이터 호출 (Call only)"),
    server: str | None = typer.Option(None, "--server", "-s"),
    port: int | None = typer.Option(None, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """엘리베이터 호출. 취소는 지원하지 않음."""
    if not call:
        logger.error("Specify --call explicitly.")
        raise typer.Exit(code=2)
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, server, port)
    payload = {DEVICE_ELEVATOR: PAYLOAD_ON}
    asyncio.run(_send(app_config, DEVICE_ELEVATOR, "", payload))

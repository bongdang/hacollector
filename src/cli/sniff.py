import asyncio
import json
from datetime import datetime

import typer
from loguru import logger

from cli._common import load_app_config
from tcphandler.kocom_tcp import KocomHandler, KocomPacket
from tcphandler.lgac485_tcp import LGACPacket, LGACPacketHandler


app = typer.Typer(no_args_is_help=True, add_completion=False)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _fmt_payload(payload) -> str:
    if isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return str(payload)


async def _sniff_kocom_loop(app_config, raw: bool) -> None:
    handler = KocomHandler(app_config)
    await handler.async_prepare_communication()
    logger.info(f"connected to Kocom EW11 [{app_config.kocom_server}:{app_config.kocom_port}] — listening")
    try:
        while True:
            header_type, chunk = await handler.async_get_one_chunk()
            if not chunk:
                continue
            packet = KocomPacket(chunk)
            try:
                notify, device, room, payload = packet.parse_data_from_packet()
            except Exception as e:
                logger.warning(f"parse failed: {e} hex={chunk.hex()}")
                continue
            tag = header_type.name if hasattr(header_type, "name") else str(header_type)
            line = (
                f"[{_ts()}] {tag:<8} device={device or '-':<14} room={room or '-':<12} "
                f"notify={notify} payload={_fmt_payload(payload)}"
            )
            if raw:
                line += f"  raw={chunk.hex()}"
            print(line, flush=True)
    finally:
        await handler.comm.close_async_socket()


async def _sniff_aircon_loop(app_config, raw: bool) -> None:
    handler = LGACPacketHandler(app_config)
    await handler.comm.connect_async_socket()
    logger.info(f"connected to LG AC EW11 [{app_config.aircon_server}:{app_config.aircon_port}] — listening")
    try:
        while True:
            body = await handler.async_read_one_chunk()
            if body is None:
                continue
            packet = LGACPacket()
            if not packet.set_packet_data(body):
                if raw:
                    print(f"[{_ts()}] decode-fail raw={body.hex()}", flush=True)
                continue
            line = (
                f"[{_ts()}] groupid={packet.groupandid:#04x} action={packet.str_action or '-':<6} "
                f"mode={packet.str_opmode or '-':<8} fan={packet.str_fanmode or '-':<6} "
                f"swing={packet.str_fanmove or '-':<5} set={packet.set_temp} cur={packet.current_temp}"
            )
            if raw:
                line += f"  raw={body.hex()}"
            print(line, flush=True)
    finally:
        await handler.comm.close_async_socket()


def _apply_overrides(app_config, attr_server, attr_port, server, port) -> None:
    if server is not None:
        setattr(app_config, attr_server, server)
    if port is not None:
        setattr(app_config, attr_port, str(port))


@app.command()
def kocom(
    server: str | None = typer.Option(None, "--server", "-s", help="EW11 호스트 (기본: KOCOM_SERVER_IP)"),
    port: int | None = typer.Option(None, "--port", "-p", help="EW11 포트 (기본: KOCOM_SERVER_PORT)"),
    raw: bool = typer.Option(False, "--raw", help="hex 페이로드 동시 출력"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """Kocom 월패드 EW11 패시브 모니터 (Ctrl-C 종료)."""
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, "kocom_server", "kocom_port", server, port)
    if not app_config.kocom_server:
        logger.error("Kocom host not set. Use --server or configure KOCOM_SERVER_IP.")
        raise typer.Exit(code=2)
    try:
        asyncio.run(_sniff_kocom_loop(app_config, raw))
    except KeyboardInterrupt:
        logger.info("interrupted")


@app.command()
def aircon(
    server: str | None = typer.Option(None, "--server", "-s", help="EW11 호스트 (기본: LGAIRCON_SERVER_IP)"),
    port: int | None = typer.Option(None, "--port", "-p", help="EW11 포트 (기본: LGAIRCON_SERVER_PORT)"),
    raw: bool = typer.Option(False, "--raw", help="hex 페이로드 동시 출력"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """LG 시스템에어컨 EW11 패시브 모니터 (Ctrl-C 종료)."""
    app_config = load_app_config(verbose=verbose)
    _apply_overrides(app_config, "aircon_server", "aircon_port", server, port)
    if not app_config.aircon_server:
        logger.error("LG AC host not set. Use --server or configure LGAIRCON_SERVER_IP.")
        raise typer.Exit(code=2)
    try:
        asyncio.run(_sniff_aircon_loop(app_config, raw))
    except KeyboardInterrupt:
        logger.info("interrupted")

import json
import sys
import time
from datetime import datetime

import paho.mqtt.client as pahomqtt
import typer
from loguru import logger

from cli._common import load_app_config


app = typer.Typer(no_args_is_help=True, add_completion=False)


def _build_client(
    host_override: str | None,
    port_override: int | None,
    user_override: str | None,
    password_override: str | None,
    anonymous: bool | None,
    verbose: bool,
) -> tuple[pahomqtt.Client, str, int]:
    """기존 MqttHandler 의 인증 패턴과 동일하게 paho 클라이언트를 구성한다."""
    app_config = load_app_config(verbose=verbose)

    host = host_override or app_config.mqtt_server
    port = port_override if port_override is not None else int(app_config.mqtt_port or 1883)
    if not host:
        logger.error("MQTT host not set. Use --host or configure MQTT_SERVER_IP.")
        raise typer.Exit(code=2)

    user = user_override if user_override is not None else app_config.mqtt_id
    password = password_override if password_override is not None else app_config.mqtt_pw
    is_anonymous = anonymous if anonymous is not None else (app_config.mqtt_anonymous == "True")

    client = pahomqtt.Client(callback_api_version=pahomqtt.CallbackAPIVersion.VERSION2)
    if not is_anonymous and user and password:
        client.username_pw_set(username=user, password=password)
        logger.debug(f"MQTT [{host}:{port}] authenticated as {user}")
    else:
        logger.debug(f"MQTT [{host}:{port}] anonymous")

    return client, host, port


def _format_payload(payload: bytes) -> str:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary {len(payload)} bytes: {payload.hex()}>"
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    except (json.JSONDecodeError, ValueError):
        return text


@app.command()
def subscribe(
    topics: list[str] = typer.Argument(..., help="구독 토픽 (와일드카드 #, + 지원). 여러 개 지정 가능."),
    qos: int = typer.Option(0, "--qos", "-q", min=0, max=2, help="QoS 레벨"),
    host: str | None = typer.Option(None, "--host", "-h", help="MQTT 호스트 (기본: config)"),
    port: int | None = typer.Option(None, "--port", "-p", help="MQTT 포트 (기본: config)"),
    user: str | None = typer.Option(None, "--user", "-u", help="MQTT 사용자 (기본: config)"),
    password: str | None = typer.Option(None, "--password", "-P", help="MQTT 비밀번호 (기본: config)"),
    anonymous: bool = typer.Option(False, "--anonymous", help="익명 접속 강제"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """토픽 라이브 모니터링 (Ctrl-C 로 종료)."""
    client, mqtt_host, mqtt_port = _build_client(host, port, user, password, anonymous or None, verbose)

    def on_connect(c, _userdata, _flags, reason_code, _props=None):
        if reason_code != 0:
            logger.error(f"MQTT connect failed: {reason_code}")
            raise typer.Exit(code=1)
        for t in topics:
            c.subscribe(t, qos=qos)
            logger.info(f"subscribed: {t} (qos={qos})")

    def on_message(_c, _userdata, msg):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{ts}] {msg.topic} {_format_payload(msg.payload)}", flush=True)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(mqtt_host, mqtt_port, keepalive=60)
    except OSError as e:
        logger.error(f"MQTT connect failed [{mqtt_host}:{mqtt_port}]: {e}")
        raise typer.Exit(code=1)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        logger.info("interrupted")
    finally:
        client.disconnect()


@app.command()
def publish(
    topic: str = typer.Argument(..., help="발행 토픽"),
    payload: str = typer.Argument("", help="페이로드 (빈 문자열 가능)"),
    qos: int = typer.Option(0, "--qos", "-q", min=0, max=2, help="QoS 레벨"),
    retain: bool = typer.Option(False, "--retain", "-r", help="retained 메시지로 발행"),
    host: str | None = typer.Option(None, "--host", "-h", help="MQTT 호스트 (기본: config)"),
    port: int | None = typer.Option(None, "--port", "-p", help="MQTT 포트 (기본: config)"),
    user: str | None = typer.Option(None, "--user", "-u", help="MQTT 사용자 (기본: config)"),
    password: str | None = typer.Option(None, "--password", "-P", help="MQTT 비밀번호 (기본: config)"),
    anonymous: bool = typer.Option(False, "--anonymous", help="익명 접속 강제"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """단발 발행. 발행 완료까지 대기 후 종료."""
    client, mqtt_host, mqtt_port = _build_client(host, port, user, password, anonymous or None, verbose)
    try:
        client.connect(mqtt_host, mqtt_port, keepalive=60)
    except OSError as e:
        logger.error(f"MQTT connect failed [{mqtt_host}:{mqtt_port}]: {e}")
        raise typer.Exit(code=1)
    client.loop_start()
    try:
        info = client.publish(topic, payload, qos=qos, retain=retain)
        info.wait_for_publish(timeout=5)
        if not info.is_published():
            logger.error("publish timeout")
            raise typer.Exit(code=1)
        logger.info(f"published: {topic} (qos={qos}, retain={retain})")
    finally:
        client.loop_stop()
        client.disconnect()


@app.command()
def discovery(
    timeout: float = typer.Option(3.0, "--timeout", "-t", help="retained 메시지 수집 시간(초)"),
    prefix: str = typer.Option("homeassistant", "--prefix", help="HA discovery prefix"),
    host: str | None = typer.Option(None, "--host", "-h", help="MQTT 호스트 (기본: config)"),
    port: int | None = typer.Option(None, "--port", "-p", help="MQTT 포트 (기본: config)"),
    user: str | None = typer.Option(None, "--user", "-u", help="MQTT 사용자 (기본: config)"),
    password: str | None = typer.Option(None, "--password", "-P", help="MQTT 비밀번호 (기본: config)"),
    anonymous: bool = typer.Option(False, "--anonymous", help="익명 접속 강제"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="디버그 로그 출력"),
) -> None:
    """HA discovery retained 메시지를 일정 시간 수집해 그룹별로 출력."""
    client, mqtt_host, mqtt_port = _build_client(host, port, user, password, anonymous or None, verbose)
    collected: dict[str, bytes] = {}

    def on_connect(c, _userdata, _flags, reason_code, _props=None):
        if reason_code != 0:
            logger.error(f"MQTT connect failed: {reason_code}")
            raise typer.Exit(code=1)
        for depth in ("+/+/config", "+/+/+/config"):
            c.subscribe(f"{prefix}/{depth}", qos=0)

    def on_message(_c, _userdata, msg):
        collected[msg.topic] = msg.payload

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(mqtt_host, mqtt_port, keepalive=60)
    except OSError as e:
        logger.error(f"MQTT connect failed [{mqtt_host}:{mqtt_port}]: {e}")
        raise typer.Exit(code=1)
    client.loop_start()
    try:
        time.sleep(timeout)
    finally:
        client.loop_stop()
        client.disconnect()

    if not collected:
        logger.warning(f"no retained discovery messages under {prefix}/ within {timeout}s")
        raise typer.Exit(code=1)

    by_component: dict[str, list[str]] = {}
    for topic in sorted(collected):
        parts = topic.split("/")
        component = parts[1] if len(parts) > 1 else "?"
        by_component.setdefault(component, []).append(topic)

    for component, topics in by_component.items():
        logger.info(f"[{component}] {len(topics)} entries")
        for t in topics:
            print(f"  {t}  {_format_payload(collected[t])}", flush=True)

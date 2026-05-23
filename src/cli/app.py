import typer

from cli import aircon, kocom, mqtt, sniff


app = typer.Typer(
    help="HACollector 진단 CLI — EW11/MQTT/디바이스 동작을 docker 없이 점검.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(aircon.app, name="aircon", help="LG 시스템에어컨 상태 조회 및 제어")
app.add_typer(kocom.app, name="kocom", help="Kocom 월패드 디바이스 상태 조회 및 제어")
app.add_typer(mqtt.app, name="mqtt", help="MQTT 토픽 구독/발행, HA discovery 점검")
app.add_typer(sniff.app, name="sniff", help="EW11 패킷 패시브 모니터링 (read-only)")

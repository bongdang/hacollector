# HACollector
hacollector는 Home Assitant에서 RS485 프로토콜을 지원하는 아파트를 제어하고 정보를 보여주기 위해 mqtt를 사용해서 정보를 주고 받는 파이썬 어플리케이션입니다. 

(주의)  이 버전은 Kocom 월패드, LG System Aircon만 지원합니다.

## 기능
1. 현재 KOCOM 월패드, LG System Aircon을 기준으로 개발되었고, 다음과 같은 기기의 컨트롤 혹은 모니터링이 가능합니다.
	1. 전등
		1. On/Off
	2. 플러그
		1. On/Off
	3. 난방
		1. 온도조절
		2. 난방
		3. 송풍
		4. 전원
	4. 공기순환기(Himpel)
		1. On/Off
		2. 세기 조절
		3. CO2 농도 센서 기능
	5. 도시가스
		1. Off Only(for Safety).
	6. 엘리베이터
		1. Call Only
	7. 시스템에어컨(LG) 
		1. 온도조절
		2. 냉방
		3. 제습
		4. 송풍
		5. 전원
2. **운영 안정성** — MQTT 브로커 재시작 후 자동 재구독, EW11 게이트웨이 무응답 시 자동 재연결을 지원합니다.

## 요구사항
아파트 환경:
	RS485프로토콜을 지원하는 Kokomo Wallpad.
	LG System Aircon.

시스템 : 
	OS : 리눅스 혹은 MacOS
	MQTT: mosquitto mqtt
	Python: 3.9.7 이상
	paho-mqtt: 1.x (`<2.0`) — `requirements.txt`에 고정. 2.x는 콜백 API가 달라 그대로 동작하지 않습니다.

장비 : EW11 RS485 Modbus to Ethernet Gateway
	2EA : Kocom WallPad용 1개, LG System Aircon용 1개
 
## 주요 설명
1. EW11을 설치하고 테스트하는 방법은 HA동호회 등에서 관련 정보를 참고 하십시오. 여기서는 정상적으로 설치 되고 동작한다는 가정을 합니다.
2. 다양한 버전을 참고하여 개발하였습니다. 설정파일 등이 기존에 공개된 프로그램에 사용하던 방식과 유사한 부분이 많습니다. 기본적으로 config.py를 수정해서 바꿀 수 있습니다.
3. thread를 사용하지 않고, asyncio를 사용하고 있습니다.
4. Python-dotenv를 사용하여 .env파일에서 일부분의 정보를 읽어들입니다. (주로 테스트용입니다.)
5. Dockerfile을 예제로 제공합니다(베이스 이미지: `python:3.13-slim`). 설정 파일(`hacollector.conf`, `.env`)은 이미지에 포함하지 않고 런타임에 마운트하거나 환경변수로 주입하는 방식을 권장합니다. 로그 파일은 loguru 빌트인 rotation으로 컨테이너 안 `/var/log/hacollector/`에 1MB × 10개로 회전 보관되며, docker-compose의 json-file 로그 드라이버에도 `max-size: 10m, max-file: 5` 제한이 걸려 있습니다.
   - 로그는 두 갈래로 나갑니다. **콘솔/도커 로그(stderr)** 는 `CONF_LOGLEVEL`(기본 `info`)로 실시간 동작을 보여주고, **파일 로그**는 기본적으로 **WARNING 이상**만 남겨 평소엔 거의 비어 있습니다(정상 동작 추적은 `docker logs`로). 파일 레벨은 `FILE_LOGLEVEL`로 조정합니다. 단, 프로세스가 (재)시작될 때마다 `===== <서비스> started =====` 배너가 레벨과 무관하게 파일에 1줄 남아 **재부팅/재시작 시점을 추적**할 수 있습니다.
6. Himpel 공기순환기에 대한 자료가 없어서 완벽하지는 않지만, Himpel에서 제공하는 CO2 농도 센서를 추가 했습니다.
7. LG System Aircon의 경우에 패킷을 분석해서 공유해 주신 여러분들 덕분에 모든 기능은 아니지만 여름에 필요한 정도는 구현이 되어있습니다. 
(정리가 덜 되어서 엉성한 코드지만 작년 한 해 만들어서 잘 사용했고, 필요하신 분들이 계실 것 같아서 공유하는 가장 큰 이유 입니다.)

## 다양한 설정 방법
hacollector는 환경을 설정하는 방법이 두가지가 있습니다. config.py를 수정하는 방법과 .env를 사용해 환경변수를 세팅하는 방법을 선택적으로 사용 가능합니다.
1. config.py를 수정하는 방법
	1. 파이선 소스를 직접 수정하는 방법에 속하며, 이전 소스들이 비슷한 방식을 사용합니다. 파이선 문법에 맞춰 설정해야 하지만, 쉽게 이해하고 수정이 가능합니다.
	2. 설정할 수 있는 값이 다양하며, mqtt 토픽의 이름을 바꿀 수도 있습니다.
	3. 단, 환경변수를 추가하여 설정을 한 경우는 환경변수의 값이 우선됩니다.
2. .env파일 혹은 환경변수를 수정하는 방법
	1. 도커 이미지를 사용하는 경우나, 파이선 소스는 수정하지 않고 필요한 값만 수정하는데 유리합니다.
	2. hacollector가 접속해야 하는 MQTT서버, EW11 Gateway IP 설정, 방 이름 및 컨트롤 가능한 전등이나 플러그 설정, 디버깅 레벨 설정등이 가능합니다.
	3. 단, .env에 값이 있는 경우(환경변수에 설정해도 같습니다.) config.py의 설정 값을 대치합니다.
	4. 방 이름 설정에서 방과 방사이의 구분은 콜론(‘:’) 문자를 사용합니다.

### .env 파일 예시 (`src/.env`)

```bash
# MQTT 브로커
MQTT_SERVER_IP=192.168.1.10
MQTT_SERVER_PORT=1883

# EW11 게이트웨이 (Kocom 월패드용 / LG 에어컨용 각 1대)
KOCOM_SERVER_IP=192.168.1.20
KOCOM_SERVER_PORT=8899
LGAIRCON_SERVER_IP=192.168.1.21
LGAIRCON_SERVER_PORT=8899

# 방 이름 (콜론 구분)
ROOMS=livingroom:bedroom:room1:room2:room3

# 로그 레벨
#   CONF_LOGLEVEL : 콘솔/도커 로그(stderr) 레벨 (debug | info | warning | error)
#   FILE_LOGLEVEL : 파일 로그(/var/log/hacollector/*.log) 레벨. 기본 warning.
#                   평소엔 심각한 이벤트만 파일에 남기고, 문제 진단 시 debug로 올립니다.
CONF_LOGLEVEL=info
# FILE_LOGLEVEL=warning
```

운영 컨테이너(docker)와 아래의 진단 CLI가 **같은 `.env`를 읽습니다**. 한 번 설정해두면 양쪽 모두 동일한 환경을 공유하기 때문에 설정을 두 번 할 필요가 없습니다.

## 진단 CLI — 배포 전 미리 테스트하기

docker 컨테이너를 띄우기 전에 EW11/MQTT/디바이스가 정상적으로 통신하는지를 한 줄짜리 명령으로 확인할 수 있는 진단 도구를 함께 제공합니다. 에어컨이 응답하는지, 월패드가 명령을 받아들이는지, MQTT 브로커에 어떤 토픽이 흐르는지 등을 배포 전에 직접 만져보며 검증할 수 있어 첫 설치 시 시행착오를 크게 줄여줍니다.

운영 의존성과 완전히 분리되어 있어 운영 도커 이미지에는 포함되지 않습니다. 위에서 작성한 `.env`를 그대로 사용합니다.

### 설치

```bash
pip install -r requirements-dev.txt
cd src
python -m cli --help
```

`requirements-dev.txt`는 운영 의존성(`paho-mqtt`, `python-dotenv`, `loguru`)에 `typer`만 추가한 형태입니다.

### 그룹 개요

| 그룹 | 용도 |
|------|------|
| `aircon` | LG 에어컨 상태 조회 / 켜기·끄기 / 패킷 디코드 |
| `kocom` | 월패드 디바이스 제어 (전등 · 플러그 · 난방 · 공기순환기 · 가스 · 엘리베이터) / 패킷 디코드 |
| `sniff` | EW11 패시브 모니터링 — RS485 버스에 흐르는 모든 패킷을 사람이 읽을 수 있는 형태로 라이브 표시 (read-only) |
| `mqtt` | MQTT 브로커 점검 — 토픽 라이브 구독 / 단발 발행 / HA discovery 덤프 |

각 서브커맨드의 옵션은 `python -m cli <그룹> <커맨드> --help`로 확인합니다.

### 1) 전등 켜기/끄기 (`kocom light`)

거실 전등 1번만 켜기:
```bash
python -m cli kocom light --room livingroom --on '1'
```

거실 전등 1번과 3번 동시에 켜기:
```bash
python -m cli kocom light --room livingroom --on '1,3'
```

거실 전등 모두 끄기:
```bash
python -m cli kocom light --room livingroom --on ''
```

지정하지 않은 번호는 모두 끄기로 처리됩니다(Kocom 프로토콜이 방 전체 상태를 한 번에 전송하기 때문). `--count`로 방의 전등 개수를 바꿀 수 있습니다(기본 3).

플러그·난방·공기순환기·가스밸브·엘리베이터도 같은 방식입니다:
```bash
python -m cli kocom plug --room kitchen --on '1,2'
python -m cli kocom thermostat --room bedroom --mode heat --target 22
python -m cli kocom thermostat --room bedroom --mode off
python -m cli kocom fan --speed low
python -m cli kocom gas --off               # 안전상 off만 지원
python -m cli kocom elevator --call         # call만 지원
```

### 2) 에어컨 켜기/끄기 (`aircon`)

현재 상태 조회:
```bash
python -m cli aircon status --id 1
```

전원 켜기 + 설정 (냉방, 25°C, 약풍, 풍향 고정):
```bash
python -m cli aircon set --id 1 --mode cool --temp 25 --fan low --swing fixed
```

전원 끄기:
```bash
python -m cli aircon off --id 1
```

옵션값 요약:
- `--mode` : `cool` | `heat` | `dry` | `fan_only` | `auto`
- `--fan` : `low` | `medium` | `high` | `auto` | `silent` | `power`
- `--swing` : `fixed` | `swing`
- `--temp` : 18~30

### 3) 패킷 모니터링 (`sniff`)

EW11에 read-only로 추가 접속해서 RS485 버스에 흐르는 모든 패킷을 실시간으로 사람이 읽을 수 있는 형태로 표시합니다. **버스에 절대 쓰지 않으므로** 운영 컨테이너가 떠 있어도 안전하게 동시 실행할 수 있습니다 (EW11이 다중 클라이언트 모드여야 함).

월패드 패킷 모니터:
```bash
python -m cli sniff kocom               # 디코드만
python -m cli sniff kocom --raw         # 디코드 + hex 동시
```

LG 에어컨 패킷 모니터:
```bash
python -m cli sniff aircon --raw
```

실제 출력 예:
```
[16:17:29.529] Normal   device=thermostat     room=livingroom   notify=True payload={"mode":"heat","current_temp":27,"target_temp":22}
[16:17:33.834] Normal   device=plug           room=livingroom   notify=True payload={"plug1":"on","plug2":"on","plug0":"on"}
[16:17:38.606] Normal   device=gas            room=wallpad      notify=True payload={"gas":"on"}
```

대표적인 활용:
- 새로운 디바이스가 보내는 raw 패킷을 캡처해서 직접 분석할 때 (`--raw`로 hex가 같이 표시됩니다)
- `kocom light` 같은 명령을 보낸 후 실제로 월패드가 응답하는지 즉시 확인할 때
- HA에서 ON/OFF 토글했을 때 어떤 RS485 패킷이 흐르는지 비교할 때

캡처한 hex를 나중에 다시 사람이 읽는 형태로 보고 싶다면:
```bash
python -m cli kocom decode 30dc003600010000110016001b00000287
python -m cli aircon decode 1002a3300000504b6d6d6d2800184519
```

### 4) MQTT 점검 (`mqtt`)

브로커만 있으면 EW11이나 docker 없이도 동작합니다. 토픽 이름이 의도한 대로 흐르는지, HA discovery payload가 올바르게 등록됐는지를 확인할 때 씁니다.

모든 토픽 라이브 구독 (Ctrl-C로 종료):
```bash
python -m cli mqtt subscribe '#'
```

특정 패턴만 모니터:
```bash
python -m cli mqtt subscribe 'homeassistant/#'        # HA discovery + state
python -m cli mqtt subscribe 'hacollector/+/set/#'    # 명령 토픽만
python -m cli mqtt subscribe 'hacollector/bridge/#'   # bridge 이벤트
```

임의 토픽 발행 (테스트용):
```bash
python -m cli mqtt publish 'hacollector/light/set/livingroom' '{"light1":"on"}'
python -m cli mqtt publish 'hacollector/aircon/set/livingroom' 'OFF' --retain
```

HA discovery retained 메시지 일괄 덤프 (component별로 그룹화):
```bash
python -m cli mqtt discovery --timeout 5
```

다른 브로커로 직접 (config 무시):
```bash
python -m cli mqtt subscribe '#' --host other.broker.local --port 1883 --anonymous
```

### 5) 권장 디버깅 워크플로우

새 디바이스를 추가하거나 문제 상황을 추적할 때 터미널을 셋 띄워두는 것이 가장 빠릅니다.

```bash
# 터미널 A — RS485 패킷이 실시간으로 흐르는지 본다
python -m cli sniff kocom --raw

# 터미널 B — MQTT 쪽도 같이 본다
python -m cli mqtt subscribe 'hacollector/#'

# 터미널 C — 직접 명령을 보낸다
python -m cli kocom fan --speed low
```

C에서 명령을 보내면 A에 약 1초 안에 월패드의 echo 패킷이 보이고, B에는 HA가 인지하는 MQTT 토픽 변화가 표시됩니다. 어느 단계에서 문제가 생기는지 한눈에 파악할 수 있습니다.

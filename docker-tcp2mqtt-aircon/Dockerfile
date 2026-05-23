FROM python:3.13-slim

RUN apt-get update && apt-get install tzdata -y
ENV TZ="Asia/Seoul"

RUN mkdir -p /tcp2mqtt_aircon/common
RUN mkdir -p /tcp2mqtt_aircon/devices
RUN mkdir -p /tcp2mqtt_aircon/tcphandler
RUN mkdir -p /tcp2mqtt_aircon/handlers

COPY src/common/*.py /tcp2mqtt_aircon/common/
COPY src/devices/*.py /tcp2mqtt_aircon/devices/
COPY src/handlers/*.py /tcp2mqtt_aircon/handlers/
COPY src/tcphandler/*.py /tcp2mqtt_aircon/tcphandler/
COPY src/tcp2mqtt_aircon.py /tcp2mqtt_aircon
COPY src/config.py /tcp2mqtt_aircon
COPY src/consts.py /tcp2mqtt_aircon
COPY src/run_loop.sh /tcp2mqtt_aircon

COPY requirements.txt /tcp2mqtt_aircon

WORKDIR /tcp2mqtt_aircon

RUN pip3 install -r requirements.txt
RUN chmod +x ./run_loop.sh

ENTRYPOINT ["./run_loop.sh"]

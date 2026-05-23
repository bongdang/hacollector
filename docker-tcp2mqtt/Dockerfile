FROM python:3.13-slim

RUN apt-get update && apt-get install tzdata -y
ENV TZ="Asia/Seoul"

RUN mkdir -p /tcp2mqtt/common
RUN mkdir -p /tcp2mqtt/devices
RUN mkdir -p /tcp2mqtt/tcphandler
RUN mkdir -p /tcp2mqtt/handlers

COPY src/common/*.py /tcp2mqtt/common/
COPY src/devices/*.py /tcp2mqtt/devices/
COPY src/handlers/*.py /tcp2mqtt/handlers/
COPY src/tcphandler/*.py /tcp2mqtt/tcphandler/
COPY src/tcp2mqtt.py /tcp2mqtt
COPY src/config.py /tcp2mqtt
COPY src/consts.py /tcp2mqtt

COPY requirements.txt /tcp2mqtt

WORKDIR /tcp2mqtt

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python", "tcp2mqtt.py"]

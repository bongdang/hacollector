FROM python:3.13-slim

RUN apt-get update && apt-get install tzdata -y
ENV TZ="Asia/Seoul"

RUN mkdir -p /hacollector/common
RUN mkdir -p /hacollector/devices
RUN mkdir -p /hacollector/tcphandler
RUN mkdir -p /hacollector/handlers

COPY src/common/*.py /hacollector/common/
COPY src/devices/*.py /hacollector/devices/
COPY src/handlers/*.py /hacollector/handlers/
COPY src/tcphandler/*.py /hacollector/tcphandler/
COPY src/hacollector.py /hacollector
# COPY src/appconf.py /hacollector
COPY src/config.py /hacollector
COPY src/consts.py /hacollector

COPY requirements.txt /hacollector

WORKDIR /hacollector

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python", "hacollector.py"]

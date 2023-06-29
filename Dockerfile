FROM python:3.11

RUN apt-get update && apt-get install tzdata -y
ENV TZ="Asia/Seoul"

RUN mkdir -p /hacollector/classes
COPY hacollector.py /hacollector
COPY classes/*.py /hacollector/classes/
COPY config.py /hacollector
COPY consts.py /hacollector
COPY hacollector.conf /hacollector
COPY .env /hacollector/

COPY requirements.txt /hacollector

WORKDIR /hacollector

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python", "hacollector.py"]
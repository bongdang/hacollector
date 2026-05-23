#!/bin/sh
# Keep the shell loop as a safety net for hard crashes (SEGV/OOM) that
# Python's own restart loop cannot catch. stderr/stdout flow to docker logs;
# rotated file logging is handled by loguru (/var/log/hacollector/).
while true; do
  python tcp2mqtt_aircon.py
  sleep 3
done

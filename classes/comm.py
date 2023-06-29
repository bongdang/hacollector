from __future__ import annotations

import asyncio
import errno
import time

from classes.utils import Color, ColorLog


class TCPComm:
    def __init__(self, server: str, port: int, buffer_size: int = 2048, interval: float = 0.0) -> None:
        self.server                     = server
        self.port                       = int(port)
        self.buffer_size                = buffer_size
        self.interval                   = interval
        self.last_accessed_time         = time.monotonic()
        self.read_buffer: bytes         = b''
        self.connection_reset: bool     = False
        self.reader: asyncio.StreamReader
        self.writer: asyncio.StreamWriter

    @classmethod
    async def async_init(cls, server: str, port: int, buffer_size: int = 2048, interval: float = 0.0):
        return cls(server, port, buffer_size, interval)

    async def async_make_connection(self):
        (self.reader, self.writer) = await asyncio.open_connection(host=self.server, port=self.port)
        self.socket = self.writer.get_extra_info('socket')

    async def connect_async_socket(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.server, int(self.port))

    async def close_async_socket(self):
        self.writer.close()
        await self.writer.wait_closed()

    def set_interval(self, interval: float):
        self.interval = interval

    def is_passed_safty_interval(self) -> bool:
        if time.monotonic() > self.last_accessed_time + self.interval:
            return True
        else:
            return False

    async def wait_safe_communication(self) -> None:
        if not self.is_passed_safty_interval():
            await asyncio.sleep(self.interval)

    async def async_write_one_chunk(self, packet: bytes) -> bool:

        await self.wait_safe_communication()

        try:
            self.writer.write(packet)
            await self.writer.drain()
            self.last_accessed_time = time.monotonic()
            return True
        except Exception as e:
            color_log = ColorLog()
            color_log.log(f"Write to Kocom RS485 fail{e}", Color.Cyan, ColorLog.Level.WARN)
            return False

    async def async_get_data_from_buffer(self, length: int) -> bytes:
        '''
        return b'' means connection closed. if reset case, self.connection_reset is True
        '''
        try:
            while length > len(self.read_buffer):
                try:
                    buffer = await self.reader.read(self.buffer_size)
                except IOError as e:
                    if e.errno == errno.ECONNRESET:
                        buffer = b''
                        self.connection_reset = True
                    raise
                self.read_buffer += buffer
            ret = self.read_buffer[0:length]
            self.read_buffer = self.read_buffer[length:]
        except Exception as e:
            color_log = ColorLog()
            color_log.log(f"Exception in socket READ: {e}", Color.Red, ColorLog.Level.CRITICAL)
            ret = b''
        return ret

    async def async_get_data_direct(self, length: int) -> bytes:
        '''
        return b'' means connection closed. if reset case, self.connection_reset is True
        '''
        try:
            buffer = await self.reader.read(length)
        except IOError as e:
            buffer = b''
            if e.errno == errno.ECONNRESET:
                self.connection_reset = True
        return buffer

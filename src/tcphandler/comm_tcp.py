import asyncio
import errno
import time

from loguru import logger


class TCPComm:
    def __init__(self, server: str, port: int, buffer_size: int = 2048, interval: float = 0.0, read_timeout: float = 10.0) -> None:
        self.server                     = server
        self.port                       = int(port)
        self.buffer_size                = buffer_size
        self.interval                   = interval
        self.read_timeout               = read_timeout
        self.last_accessed_time         = time.monotonic()
        self.read_buffer: bytes         = b''
        self.connection_reset: bool     = False
        self.reader: asyncio.StreamReader
        self.writer: asyncio.StreamWriter

        self._io_event: asyncio.Event   = asyncio.Event()
        self._io_event.set()            # initially free

    @classmethod
    async def async_init(cls, server: str, port: int, buffer_size: int = 2048, interval: float = 0.0):
        return cls(server, port, buffer_size, interval)

    async def async_make_connection(self):
        (self.reader, self.writer) = await asyncio.open_connection(host=self.server, port=self.port)
        self.socket = self.writer.get_extra_info('socket')

    async def connect_async_socket(self) -> None:
        # If connection is stale or reset, close old connection first
        if hasattr(self, 'writer') and self.writer is not None:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

        self.reader, self.writer = await asyncio.open_connection(self.server, int(self.port))
        self.connection_reset = False
        self.read_buffer = b''

    async def close_async_socket(self):
        writer = getattr(self, 'writer', None)
        if writer is None:
            return
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    def set_interval(self, interval: float):
        self.interval = interval

    def is_passed_safty_interval(self) -> bool:
        if time.monotonic() > self.last_accessed_time + self.interval:
            return True
        else:
            return False

    async def wait_safe_communication(self) -> None:
        next_access_time = self.last_accessed_time + self.interval
        remain = next_access_time - time.monotonic()
        if remain > 0:
            await asyncio.sleep(remain)

    def enter_processing(self) -> None:
        self._io_event.clear()

    def leave_processing(self) -> None:
        self._io_event.set()

    @property
    def is_processing(self) -> bool:
        return not self._io_event.is_set()

    async def get_access_ticket(self) -> None:
        await self._io_event.wait()

    async def async_write_one_chunk(self, packet: bytes) -> bool:
        logger.debug(f">>Write to RS485 [{packet.hex()}]. Start")
        ret: bool = True
        try:
            await self.get_access_ticket()
            self.enter_processing()
            await self.wait_safe_communication()
            self.writer.write(packet)
            await self.writer.drain()
            self.last_accessed_time = time.monotonic()
        except Exception as e:
            logger.warning(f"Write to Kocom RS485 fail{e}")
            ret = False
        finally:
            self.leave_processing()

        logger.debug(f"<<Write to RS485 [{packet.hex()}]. Done")
        return ret

    MAX_CONSECUTIVE_TIMEOUTS = 10  # treat as connection lost after this many consecutive timeouts

    async def async_get_data_from_buffer(self, length: int) -> bytes:
        '''
        return b'' means connection closed. if reset case, self.connection_reset is True
        '''
        logger.debug(">>Read from RS485 Start")
        ret: bytes = b''
        consecutive_timeouts = 0
        try:
            while length > len(self.read_buffer):
                try:
                    buffer = await asyncio.wait_for(
                        self.reader.read(self.buffer_size),
                        timeout=self.read_timeout
                    )
                    consecutive_timeouts = 0  # reset on any successful read
                except asyncio.TimeoutError:
                    # Timeout is normal for idle connections (e.g., Kocom waits for wallpad changes)
                    # Yield control to event loop to allow MQTT/other tasks to run, then retry
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= self.MAX_CONSECUTIVE_TIMEOUTS:
                        logger.warning(f"Read timeout {consecutive_timeouts} times in a row - treating as connection lost")
                        self.connection_reset = True
                        return b''
                    logger.debug(f"Read timeout after {self.read_timeout}s ({consecutive_timeouts}/{self.MAX_CONSECUTIVE_TIMEOUTS}) - yielding")
                    await asyncio.sleep(0)  # Yield control to event loop
                    continue  # Retry reading
                except IOError as e:
                    if e.errno == errno.ECONNRESET:
                        self.connection_reset = True
                        return b''
                    raise

                if buffer == b'':
                    # Actual EOF - connection closed by remote
                    self.connection_reset = True
                    return b''

                self.read_buffer += buffer

            ret = self.read_buffer[0:length]
            self.read_buffer = self.read_buffer[length:]
        except Exception as e:
            logger.critical(f"Exception in socket READ: {e}")
            ret = b''

        logger.debug(f"<<Read from RS485 [{ret.hex()}]. Done")
        return ret

    async def async_get_data_direct(self, length: int) -> bytes:
        '''
        return b'' means connection closed. if reset case, self.connection_reset is True
        '''
        try:
            buffer = await asyncio.wait_for(
                self.reader.read(length),
                timeout=self.read_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Direct read timeout after {self.read_timeout}s - treating as connection lost")
            self.connection_reset = True
            return b''
        except IOError as e:
            buffer = b''
            if e.errno == errno.ECONNRESET:
                self.connection_reset = True
        except Exception as e:
            logger.warning(f"Exception in direct socket READ: {e}")
            self.connection_reset = True
            buffer = b''
        return buffer

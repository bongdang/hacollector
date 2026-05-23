import argparse
import asyncio
import pathlib
import socket
import sys
from enum import Enum
from struct import calcsize, pack, unpack

from loguru import logger
from common.utils import setup_logger
from consts import AIRCON_DEFAULT_TEMP


class Server(Enum):
    KOCOM = 0
    LGAC = 1


root_dir = pathlib.Path.cwd()
if not setup_logger('TCPServer', log_dir=root_dir / 'log', file_name='TCPServer.log', level='debug'):
    sys.exit(1)

logger.info("test info")
logger.warning("test warn")
logger.debug("test debug")
logger.error("test error")
logger.critical("test critical")

logger.info("Starting... TCP server for protocol testings")


class LGACHandler:
    class LGACBody:
        def __init__(self) -> None:
            self.write_body_fmt     = '>BBBBBBBBBBBBBBBB'
            self.read_body_fmt      = '>BBBBB'
            self.fill_return_head   = 0x10
            self.action             = 0
            self.fill_unknown1      = 0xa3
            self.fill_unknown2      = 0
            self.groupandid         = 0
            self.fill_unknown3      = 0
            self.current_mode       = 0
            self.set_temp           = 0
            self.current_temp       = 0
            self.pipe1_temp         = 0
            self.pipe2_temp         = 0
            self.fill_outer_sensor  = 0
            self.fill_unknown4      = 0
            self.fill_model         = 0
            self.fill_fixedvalue    = 0
            self.checksum           = 0
            return

        @property
        def get_read_packet_length(self):
            return calcsize(self.read_body_fmt)

        @property
        def get_response_packet_length(self):
            return calcsize(self.write_body_fmt)

        def calc_checksum(self, body: bytes) -> int:
            checksum = sum(body)
            return (checksum & 0xff) ^ 0x55

        def calc_aircon_temp(self, num: int) -> int:
            return (64 - num) * 3

        def pack_response_struct(self):
            self.action         = 0x03
            self.current_mode   = 0x40
            self.current_temp   = int(self.calc_aircon_temp(AIRCON_DEFAULT_TEMP + 2))
            self.set_temp       = int(self.calc_aircon_temp(AIRCON_DEFAULT_TEMP))
            self.pipe1_temp     = int(self.calc_aircon_temp(18))
            self.pipe2_temp     = int(self.calc_aircon_temp(18))
            temp_list = [
                self.fill_return_head,
                self.action,
                self.fill_unknown1,
                self.fill_unknown2,
                self.groupandid,
                self.fill_unknown3,
                self.current_mode,
                self.set_temp,
                self.current_temp,
                self.pipe1_temp,
                self.pipe2_temp,
                self.fill_outer_sensor,
                self.fill_unknown4,
                self.fill_model,
                self.fill_fixedvalue,
                self.checksum
            ]
#            test = [type(x) for x in temp_list]
#            print(test)
            pre_pack = pack(self.write_body_fmt, *temp_list)
            self.checksum = self.calc_checksum(pre_pack[:(self.get_response_packet_length - 1)])
            temp_list[-1] = self.checksum
            return pack(self.write_body_fmt, *temp_list)

        def unpack_struct(self, data):
            try:
                res = unpack(self.read_body_fmt, data)
                (
                    self.action,
                    self.groupandid,
                    self.current_mode,
                    self.set_temp,
                    self.checksum
                ) = res
                self.set_temp = (self.set_temp & 0x0f) + 0x0f
            except Exception as e:
                logger.info(f"Unpack Error {e}")
                return False
            return True

    def __init__(self) -> None:
        self.packetHeader   = b'\x80\x00\xa3'
        self.header_len     = 3

    def set_io_buffer(self, read_buffer, write_buffer):
        self.read_buffer = read_buffer
        self.write_buffer = write_buffer

    async def loop(self):
        try:
            while True:
                isok, data = await self.read_buffer(self.header_len)
                if isok and len(data) == self.header_len:
                    is_valid_packet = (self.packetHeader == data)
                    if is_valid_packet:
                        await self.handle_request()
                    else:
                        logger.info("Bad Packet and Quit!")
                        break
                break       # this is for gabage trailing bytes!
        except KeyboardInterrupt:
            logger.info("Exiting by ctrl-C")
        return

    async def handle_body_request(self, bEx=False):
        logger.info(">>>Body Reading")

        body_req = LGACHandler.LGACBody()
        isok, data = await self.read_buffer(body_req.get_read_packet_length)
        if isok:
            body_req.unpack_struct(data)

            final_data = body_req.pack_response_struct()

            logger.info(f"request OK. len={len(final_data)}")
            return final_data
        return b''              # means error

    async def handle_request(self):
        result_binary = await self.handle_body_request()
        len_result = len(result_binary)
        logger.info(f"result = {result_binary.hex()}, len = {len_result}")
        await self.write_buffer(result_binary)
        logger.info("Write Done!")


class KocomHandler:
    class kocomBody:
        def __init__(self) -> None:
            self.body_fmt   = '>BBBBBBBBBBBBBBBBB'
            self.b1         = 0
            self.b2         = 0
            self.b3         = 0
            self.b4         = 0
            self.b5         = 0
            self.b6         = 0
            self.b7         = 0
            self.b8         = 0
            self.b9         = 0
            self.b10        = 0
            self.b11        = 0
            self.b12        = 0
            self.b13        = 0
            self.b14        = 0
            self.b15        = 0
            self.b16        = 0
            self.checksum   = 0
            self.d1         = 0x0d
            self.d2         = 0x0d
            return

        def get_cls_length(self):
            return calcsize(self.body_fmt)

        def calc_checksum(self, body: bytes) -> int:
            checksum = sum(body)
            return (checksum & 0xff)

        def pack_struct(self):
            pre_pack = b'\xaa\x55' + pack(
                self.body_fmt,
                self.b1,
                self.b2,
                self.b3,
                self.b4,
                self.b5,
                self.b6,
                self.b7,
                self.b8,
                self.b9,
                self.b10,
                self.b11,
                self.b12,
                self.b13,
                self.b14,
                self.b15,
                self.b16,
                0
            )
            self.checksum = self.calc_checksum(pre_pack[:16])
            return pack(self.body_fmt,
                        self.b1,
                        self.b2,
                        self.b3,
                        self.b4,
                        self.b5,
                        self.b6,
                        self.b7,
                        self.b8,
                        self.b9,
                        self.b10,
                        self.b11,
                        self.b12,
                        self.b13,
                        self.b14,
                        self.b15,
                        self.b16,
                        self.checksum)

        def unpack_struct(self, data):
            try:
                res = unpack(self.body_fmt, data)
                (
                    self.b1,
                    self.b2,
                    self.b3,
                    self.b4,
                    self.b5,
                    self.b6,
                    self.b7,
                    self.b8,
                    self.b9,
                    self.b10,
                    self.b11,
                    self.b12,
                    self.b13,
                    self.b14,
                    self.b15,
                    self.b16,
                    self.checksum
                ) = res
            except Exception as e:
                logger.info(f"Unpack Error {e}")
                return False
            return True

    def __init__(self) -> None:
        self.packetHeader   = b'\xaa\x55'
        self.header_len     = 2

    def set_io_buffer(self, read_buffer, write_buffer):
        self.read_buffer = read_buffer
        self.write_buffer = write_buffer

    async def loop(self):
        try:
            while True:
                isok, data = await self.read_buffer(self.header_len)
                if isok and len(data) == self.header_len:
                    is_valid_packet = (self.packetHeader == data)
                    if is_valid_packet:
                        await self.handle_request_kocom()
                        isok, data = await self.read_buffer(2)
                        logger.info(f"tail = {data.hex()}")
                    else:
                        logger.info(f"Bad Packet and Quit! [{data.hex()}]")
                        continue
                # break       # break means close connection
        except KeyboardInterrupt:
            logger.info("Exiting by ctrl-C")
        return

    async def handle_body_request_kocom(self, bEx=False):
        logger.info(">>>Body Reading")

        body_req = KocomHandler.kocomBody()
        isok, data = await self.read_buffer(body_req.get_cls_length())
        if isok:
            body_req.unpack_struct(data)

            final_data = self.packetHeader + body_req.pack_struct() + b'\x0d\x0d'

            logger.info(f"request OK. len={len(final_data)}")
            return final_data
        return b''              # means error

    async def handle_request_kocom(self):
        result_binary = await self.handle_body_request_kocom()
        len_result = len(result_binary)
        logger.info(f"result = {result_binary.hex()}, len = {len_result}")
        await asyncio.sleep(10)
        # test code for fan sensor
        # await self.write_buffer(bytes.fromhex('aa5530dc00010048000011034017041f0000e30d0d'))


class MainHandler:
    def __init__(self, name):
        self.name = name
        self.reader: asyncio.StreamReader
        self.writer: asyncio.StreamWriter
        return

    def set_streams(self, reader, writer):
        self.reader = reader
        self.writer = writer
        return

    async def do_read_and_go(self):
        if self.name == Server.LGAC:
            self.handler = LGACHandler()
        else:
            self.handler = KocomHandler()

        self.handler.set_io_buffer(self.async_read_buffer, self.async_write_buffer)
        await self.handler.loop()

    async def async_read_buffer(self, bufsize):
        use_partial_read = False            # readexactly, read partial retry all failed - KKS
        data: bytes = b''
        try:
            data = await self.reader.read(bufsize)
            read_len = len(data)

            while use_partial_read and not self.reader.at_eof() and read_len != 0 and read_len < bufsize:
                chunk = await self.reader.read(bufsize - read_len)
                chunk_len = len(chunk)
                if chunk_len != 0:
                    read_len += chunk_len
                    data += chunk
                else:
                    read_len = chunk_len
        except Exception as e:
            logger.info(f"async read error {e}")

        return len(data) != 0, data

    async def async_write_buffer(self, data):
        self.writer.write(data)
        await self.writer.drain()


async def handle_LGAC_packet(reader, writer):
    clsMainProc = MainHandler(Server.LGAC)
    clsMainProc.set_streams(reader, writer)

    await clsMainProc.do_read_and_go()

    writer.close()
    await writer.wait_closed()
    logger.info("LGAC Server: connection was closed")


async def handle_kocom_packet(reader, writer):
    clsMainProc = MainHandler(Server.KOCOM)
    clsMainProc.set_streams(reader, writer)

    await clsMainProc.do_read_and_go()

    await asyncio.sleep(1)
    # writer.close()
    # await writer.wait_closed()
    logger.info("Kocom Server: connection maintained!")


async def count_down_end(secs):
    waitting_sec = 100
    for i in range(0, secs, waitting_sec):
        logger.info(f"{secs - i} seconds to end server! to quit press Ctrl-C")
        await asyncio.sleep(waitting_sec)


async def one_call_per_connect_server(ip, port, handle_LGAC_packet):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((ip, port))
    except Exception as e:
        logger.info(f"Error in socket bind [{e}]")
        return

    server = await asyncio.start_server(handle_LGAC_packet, sock=sock)
    if server is not None:
        logger.info("LGAC fake server started")
        # for do async!
        await count_down_end(3600 * 12)

        server.close()
        await server.wait_closed()

        logger.info("server was closed")


async def many_call_per_connect_server(ip, port, handle_kocom_packet):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((ip, port))
    except Exception as e:
        logger.info(f"Error in socket bind [{e}]")
        return

    server = await asyncio.start_server(handle_kocom_packet, sock=sock)
    if server is not None:
        logger.info("kocom fake server started")
        # for do async!
        await count_down_end(3600 * 12)

        server.close()
        await server.wait_closed()

        logger.info("server was closed")


async def server_asyncmain(argv):
    parser = argparse.ArgumentParser(description="how to use control server")

    parser.add_argument('--server', '-s', help="change connecting server", default='127.0.0.1')
    parser.add_argument('--port', '-p', type=int, help="change connecting port", default=8898)

    args = parser.parse_args()

    await asyncio.gather(
        one_call_per_connect_server(args.server, args.port, handle_LGAC_packet),
        many_call_per_connect_server(args.server, args.port + 1, handle_kocom_packet)
    )


if __name__ == "__main__":

    my_main = server_asyncmain

    try:
        logger.info("Starting Kocom Walpad and LGAircon emulator Server")

        asyncio.run(my_main(sys.argv))
    except KeyboardInterrupt:
        logger.info("=== Exit by Key! ===")

    logger.info("Kocom Walpad and LGAircon emulator Server is Ended")

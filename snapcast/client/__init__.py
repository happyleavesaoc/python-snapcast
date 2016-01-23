""" Snapcast Client. """

import logging
import queue
import socket
import threading
import time

from snapcast.client.messages import (hello_packet, request_packet,
                                      command_packet, packet,
                                      basemessage, BASE_SIZE)
from snapcast.client.gstreamer import GstreamerAppSrc

__version__ = '0.0.1-py'

SERVER_PORT = 1704
SYNC_AFTER = 1
BUFFER_SIZE = 30

CMD_START_STREAM = 'startStream'

MSG_SERVER_SETTINGS = 'ServerSettings'
MSG_SAMPLE_FORMAT = 'SampleFormat'
MSG_WIRE_CHUNK = 'WireChunk'
MSG_HEADER = 'Header'
MSG_TIME = 'Time'

_LOGGER = logging.getLogger(__name__)


def mac():
    """ Get MAC. """
    from uuid import getnode as get_mac
    return ':'.join(("%012x" % get_mac())[i:i+2] for i in range(0, 12, 2))


class Client:
    """ Snapcast Client. """

    def __init__(self, host, port):
        """ Setup. """
        self._queue = queue.Queue()
        self._buffer = queue.Queue()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))
        self._source = GstreamerAppSrc()
        self._last_sync = time.time()
        self._connected = False
        self._buffered = False
        threading.Thread(target=self._read_socket, daemon=True).start()
        threading.Thread(target=self._write_socket, daemon=True).start()
        threading.Thread(target=self._play, daemon=True).start()
        _LOGGER.info('Connected to %s:%s', host, port)

    def register(self):
        """ Transact with server. """
        self._queue.put(hello_packet(socket.gethostname(), mac(), __version__))
        self._queue.put(request_packet(MSG_SERVER_SETTINGS))
        self._queue.put(request_packet(MSG_SAMPLE_FORMAT))
        self._queue.put(request_packet(MSG_HEADER))

    def request_start(self):
        """ Indicate readiness to receive stream.

        This is a blocking call.
        """
        self._queue.put(command_packet(CMD_START_STREAM))
        _LOGGER.info('Requesting stream')
        self._source.run()

    def _read_socket(self):
        """ Process incoming messages from socket. """
        while True:
            base_bytes = self._socket.recv(BASE_SIZE)
            base = basemessage.parse(base_bytes)
            payload_bytes = self._socket.recv(base.payload_length)
            self._handle_message(packet.parse(base_bytes + payload_bytes))

    def _handle_message(self, data):
        """ Handle messages. """
        if data.type == MSG_SERVER_SETTINGS:
            _LOGGER.info(data.payload)
        elif data.type == MSG_SAMPLE_FORMAT:
            _LOGGER.info(data.payload)
            self._connected = True
        elif data.type == MSG_TIME:
            if not self._buffered:
                _LOGGER.info('Buffering')
        elif data.type == MSG_HEADER:
            # Push to app source and start playing.
            _LOGGER.info(data.payload.codec.decode('ascii'))
            self._source.push(data.payload.header)
            self._source.play()
        elif data.type == MSG_WIRE_CHUNK:
            # Add chunks to play queue.
            self._buffer.put(data.payload.chunk)
            if self._buffer.qsize() > BUFFER_SIZE:
                self._buffered = True
            if self._buffer.empty():
                self._buffered = False

    def _write_socket(self):
        """ Pass messages from queue to socket. """
        while True:
            now = time.time()
            if self._connected and (self._last_sync + SYNC_AFTER) < now:
                self._queue.put(request_packet(MSG_TIME))
                self._last_sync = now
            if not self._queue.empty():
                self._socket.send(self._queue.get())

    def _play(self):
        """ Relay buffer to app source. """
        while True:
            if self._buffered:
                self._source.push(self._buffer.get())

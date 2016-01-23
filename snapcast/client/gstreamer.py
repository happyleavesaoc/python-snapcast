""" GStreamer-related items. """

import gi
from gi.repository import GObject, Gst

gi.require_version('Gst', '1.0')
GObject.threads_init()
Gst.init(None)


class GstreamerAppSrc:
    """ GStreamer 1.0 App Source.

    Pipeline is like this:
    App Source -> Decode -> Queue -> Convert -> Sink

    App Source: The snapcast client pushes buffers into the source.
    Decode: Will decode for codecs supported by GStreamer (ogg, flac, etc)
    Queue: Queue for converting.
    Convert: Convert to suitable representation for Alsa.
    Sink: Alsa.
    """

    def __init__(self):
        """ Initialize app src. """
        self._mainloop = GObject.MainLoop()
        self._pipeline = Gst.Pipeline()

        # Make elements.
        self._src = Gst.ElementFactory.make('appsrc', 'appsrc')
        decode = Gst.ElementFactory.make("decodebin", "decode")
        self._queueaudio = Gst.ElementFactory.make('queue', 'queueaudio')
        audioconvert = Gst.ElementFactory.make('audioconvert', 'audioconvert')
        sink = Gst.ElementFactory.make('alsasink', 'sink')

        self._src.set_property('stream-type', 'stream')

        # Add to pipeline.
        self._pipeline.add(self._src)
        self._pipeline.add(decode)
        self._pipeline.add(self._queueaudio)
        self._pipeline.add(audioconvert)
        self._pipeline.add(sink)

        # Link elements.
        self._src.link(decode)
        self._queueaudio.link(audioconvert)
        audioconvert.link(sink)
        decode.connect('pad-added', self._decode_src_created)

    def play(self):
        """ Play. """
        self._pipeline.set_state(Gst.State.PLAYING)

    def run(self):
        """ Run - blocking. """
        self._mainloop.run()

    def push(self, buf):
        """ Push a buffer into the source. """
        self._src.emit('push-buffer', Gst.Buffer.new_wrapped(buf))

    # pylint: disable=unused-argument
    def _decode_src_created(self, element, pad):
        """ Link pad to queue. """
        pad.link(self._queueaudio.get_static_pad('sink'))

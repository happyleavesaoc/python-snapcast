""" Snapcast messages. """

from construct import (ULInt8, ULInt16, ULInt32, ULInt64,
                       Embed, Struct, Enum, Array,
                       PascalString, Switch, Container)

ENCODING = 'utf-8'
BASE_SIZE = 26

# pylint: disable=bad-continuation,invalid-name

timestamp = Embed(Struct('time',
    ULInt32('secs'),
    ULInt32('usecs')
))


snaptype = Enum(ULInt16('type'),
    Base=0,
    Header=1,
    WireChunk=2,
    SampleFormat=3,
    ServerSettings=4,
    Time=5,
    Request=6,
    Ack=7,
    Command=8,
    Hello=9,
    Map=10,
    String=11
)


basemessage = Struct('base',
    snaptype,
    ULInt16('id'),
    ULInt16('refer'),
    Struct('sent', timestamp),
    Struct('recv', timestamp),
    ULInt32('payload_length'),
)


mapmessage = Struct('map',
    ULInt16('num'),
    Array(lambda ctx: ctx.num, Struct('map',
        PascalString('field', length_field=ULInt16('length')),
        PascalString('value', length_field=ULInt16('length'))
    ))
)


stringmessage = Struct('string',
    PascalString('string', length_field=ULInt16('string_length'))
)


request = Struct('request',
    Struct('request_type', Embed(snaptype))
)


server_settings = Struct('settings',
    ULInt32('buffer_ms'),
    ULInt32('latency'),
    ULInt16('volume'),
    ULInt8('mute')
)


sample_format = Struct('sample',
    ULInt32('rate'),
    ULInt16('bits'),
    ULInt16('channels'),
    ULInt16('sample_size'),
    ULInt16('frame_size')
)


header = Struct('header',
    PascalString('codec', length_field=ULInt16('codec_length')),
    PascalString('header', length_field=ULInt32('header_length'))
)


time = Struct('header',
    ULInt64('latency')
)


chunk = Struct('chunk',
    Struct('timestamp', timestamp),
    PascalString('chunk', length_field=ULInt32('chunk_length'))
)


hello = mapmessage
command = stringmessage
ack = stringmessage


packet = Struct('packet',
    Embed(basemessage),
    Switch('payload', lambda ctx: ctx.type,
        {
            'Header': header,
            'Time': time,
            'WireChunk': chunk,
            'SampleFormat': sample_format,
            'ServerSettings': server_settings,
            'Request': request,
            'Hello': hello,
            'Command': command,
            'Ack': ack
        }
    )
)

# pylint: enable=bad-continuation,invalid-name


def message(message_type, payload, payload_length):
    """ Build a message. """
    return packet.build(
        Container(
            type=message_type,
            id=1,
            refer=0,
            sent=Container(
                secs=0,
                usecs=0
            ),
            recv=Container(
                secs=0,
                usecs=0
            ),
            payload_length=payload_length,
            payload=payload
        )
    )


def map_helper(data):
    """ Build a map message. """
    as_list = []
    length = 2
    for field, value in data.items():
        as_list.append(Container(field=bytes(field, ENCODING),
                                 value=bytes(value, ENCODING)))
        length += len(field) + len(value) + 4
    return (Container(
        num=len(as_list),
        map=as_list
    ), length)


def hello_packet(hostname, mac, version):
    """ Build a hello message. """
    return message('Hello', *map_helper({
        'HostName': hostname,
        'MAC': mac,
        'Version': version
    }))


def request_packet(request_type):
    """ Build a request message. """
    return message('Request', Container(request_type=request_type), 2)


def command_packet(cmd):
    """ Build a command message. """
    return message('Command',
                   Container(string_length=len(cmd),
                             string=bytes(cmd, ENCODING)),
                   len(cmd) + 2)

[![Build Status](https://travis-ci.org/happyleavesaoc/python-snapcast.svg?branch=master)](https://travis-ci.org/happyleavesaoc/python-snapcast) [![PyPI version](https://badge.fury.io/py/snapcast.svg)](https://badge.fury.io/py/snapcast)

# python-snapcast

Control [Snapcast](https://github.com/badaix/snapcast) in Python 3. Reads client configurations, updates clients, and receives updates from other controllers.

Supports Snapcast `0.15.0`.

## Install

`pip install snapcast`

## Usage

### Control
```python
import asyncio
import snapcast.control

loop = asyncio.get_event_loop()
server = loop.run_until_complete(snapcast.control.create_server(loop, 'localhost'))

# print all client names
for client in server.clients:
  print(client.friendly_name)

# set volume for client #0 to 50%
client = server.clients[0]
loop.run_until_complete(server.client_volume(client.identifier, {'percent': 50, 'muted': False}))
```

### Client
Note: This is experimental. Synchronization is not yet supported.
Requires GStreamer 1.0.
```python
import snapcast.client

client = snapcast.client.Client('localhost', snapcast.client.SERVER_PORT)
client.register()
client.request_start() # this blocks

```

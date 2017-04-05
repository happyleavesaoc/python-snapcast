[![Build Status](https://travis-ci.org/happyleavesaoc/python-snapcast.svg?branch=master)](https://travis-ci.org/happyleavesaoc/python-snapcast) [![PyPI version](https://badge.fury.io/py/snapcast.svg)](https://badge.fury.io/py/snapcast)

# python-snapcast

Control [Snapcast](https://github.com/badaix/snapcast) in Python 3. Reads client configurations, updates clients, and receives updates from other controllers.

Supports Snapcast `0.11.1`.

## Install

`pip install snapcast`

## Usage

### Control
```python
import snapcast.control

server = snapcast.control.Snapserver('localhost', snapcast.control.CONTROL_PORT)

for client in server.clients:
    # client is an instance of snapcast.Snapclient
    client.name = 'example'
    print(client.name) # shows 'example'
    client.volume = 100
    print(client.volume) # shows 100
    client.muted = True
    print(client.muted) # shows True
    client.latency = 0
    print(client.latency) # shows 0
    print(client.identifier) # shows 'example'
    client.name = None
    print(client.identifier) # shows ip address
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

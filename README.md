[![Build Status](https://travis-ci.org/happyleavesaoc/python-snapcast.svg?branch=master)](https://travis-ci.org/happyleavesaoc/python-snapcast) [![PyPI version](https://badge.fury.io/py/snapcast.svg)](https://badge.fury.io/py/snapcast)

# python-snapcast

Control [Snapcast](https://github.com/badaix/snapcast) in Python 3. Reads client configurations, updates clients, and receives updates from other controllers.
The connection could be made with the json-rpc or Websockets interface. Websockets is more stable due to [issue](https://github.com/badaix/snapcast/issues/1173) in snapserver. 

Supports Snapcast `0.15.0`, but works well with latest Snapcast `0.27.0`

## Install

`pip install snapcast`

## Usage

### Control
```python
import asyncio
import snapcast.control

loop = asyncio.get_event_loop()
server = loop.run_until_complete(snapcast.control.create_server(loop, 'localhost', port=1780, reconnect=True, use_websockets=True))

# print all client names
for client in server.clients:
  print(client.friendly_name)

# set volume for client #0 to 50%
client = server.clients[0]
loop.run_until_complete(server.client_volume(client.identifier, {'percent': 50, 'muted': False}))

# create background task (polling)
async def testloop():
    while(1):
        print("still running")
        #print(json.dumps(server.streams[0].properties, indent=4))
        print(server.groups)
        await asyncio.sleep(10)

test = loop.create_task(testloop())

# add callback for client #0 volume change
def my_update_func(client):
    print(client.volume)
    
server.clients[0].set_callback(my_update_func)

# keep loop running to receive callbacks and to keep background task alive
loop.run_forever()
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

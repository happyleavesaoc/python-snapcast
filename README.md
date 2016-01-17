# python-snapcast

Control [Snapcast](https://github.com/badaix/snapcast) in Python 3. Reads client configurations, updates clients, and receives updates from other controllers.

## Usage

```python
import snapcast

server = snapcast.Snapserver('localhost', snapcast.CONTROL_PORT)
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

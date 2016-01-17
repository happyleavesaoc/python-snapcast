# python-snapserver

Control Snapcast.

## Usage

```python
import snapcast

server = snapcast.Snapserver('localhost', snapcast.CONTROL_PORT)
for client in server.clients:
    client.name = 'example'
    print(client.name) # returns 'example'
```

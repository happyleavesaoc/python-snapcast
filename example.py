import argparse
import asyncio
import snapcast.control
import logging
import signal


def changed(client):
    print(client)
    print(f"{client.friendly_name} volume {client.volume}"
          f" playing: {client.stream}")


async def main(host):
    server = snapcast.control.Snapserver(
        asyncio.get_running_loop(), host)

    # Handle signals
    waiter = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, waiter.set)
    loop.add_signal_handler(signal.SIGINT, waiter.set)

    await server.start()

    for client in server.clients:
        print(f"Setting callback for {client}")
        client.set_callback(changed)

    for g in server.groups:
        print(g)

    for s in server.streams:
        print(s)

    await waiter.wait()
    server.stop()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="snapcast example")
    parser.add_argument("host", help="mpd hostname")
    args = parser.parse_args()

    logging.basicConfig(level="DEBUG")
    logging.getLogger("snapcast.control.server").setLevel("DEBUG")

    asyncio.run(main(host=args.host))

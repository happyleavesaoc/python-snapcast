#!/usr/bin/python3
#
# Display metadata for playing streams
# Author: https://github.com/frafall
#
import sys
import os
import logging
import argparse
import snapcast.control
import asyncio
import json

#logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
#logger = logging.getLogger(__name__)

def serverPort(service):
   try:
      server, port = service.split(':')

   except ValueError:
      server = service
      port   = snapcast.control.CONTROL_PORT

   else:
      port   = int(port)

   return server, port

def run_status(loop, server, port):
   return (yield from snapcast.control.create_server(loop, server, port))

def main():
   verbose = 0

   # Verbose output
   def vprint(str):
      if verbose > 0:
         print(str)

   def tag(jtag, name, default=None):
      if(name in jtag):
         return jtag[name]
      return default

   # Parse arguments
   parser = argparse.ArgumentParser()
   parser.add_argument('-v', '--verbose', action='count', default=0)
   parser.add_argument('-d', '--debug', action='store_true')
   parser.add_argument('-s', '--server', default=os.environ.get('SNAPSERVER', '127.0.0.1'))

   args = parser.parse_args()
   verbose = args.verbose
   server, port = serverPort(args.server)

   vprint("Connecting to %s port %d" %(server, port))
   loop = asyncio.get_event_loop()

   try:
      snapserver = loop.run_until_complete(run_status(loop, server, port))

   except OSError:
      print("Can't connect to %s:%d" %(server, port))

   else:
      for group in snapserver.groups:
         stream = snapserver.stream(group.stream)

         if(stream.status != 'idle'):
            title = tag(stream.meta, 'TITLE')
            artist = tag(stream.meta, 'ARTIST')
            if(title): 
               state = 'playing "%s" by %s from stream <%s>' %(title, artist, stream.friendly_name)
            else:
               state = '-idle-'
            print("Zone: %s" %(group.friendly_name))
            print("   stream: %s" %(stream.friendly_name))
            print("   artist: %s" %(artist))
            print("    title: %s" %(title))

            for client_id in group.clients:
               client = snapserver.client(client_id)
               print("  speaker: %s" %(client.friendly_name))

if __name__ == '__main__':
   main()

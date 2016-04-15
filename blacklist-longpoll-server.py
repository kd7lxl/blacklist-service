#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()

import gevent
from gevent import pywsgi
import redis


def handle(environ, start_response):
    start_response('200 OK', [
        ('Content-Type', 'text/plain'),
        ('Connection', 'close'),
    ])
    server = redis.Redis(host='localhost', port=6379, db=0)
    client = server.pubsub()
    client.subscribe('blacklist')

    content = ""

    while True:
        message = client.get_message(timeout=25.0)
        if message is None:
            content = "# timeout"
            break
        elif message['type'] == 'message':
            content = message['data']
            break
    client.close()
    return content


server = pywsgi.WSGIServer(('127.0.0.1', 1234), handle)
print "Serving on http://127.0.0.1:1234..."
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.stop()

import json
import aiohttp
import asyncio

class Subscriber:
    delimiter = b'\n\n'
    readsize = 128

    def __init__(self, subscribeURL, query, callback, args=[]):
        self.url = subscribeURL
        self.query = query
        self.cb = callback
        self.args = args

    def subscribe(self):
        try:
            print("subscribe to", self.url)
            resp = yield from aiohttp.request("POST", self.url, data=self.query)
        except Exception as e:
            print(e)
            return

        i = 0
        buffer = bytearray()
        while True:
            chunk = yield from resp.content.read(self.readsize)
            if not chunk:
                break
            buffer.extend(chunk)
            buffer, messages = self.get_messages(buffer)
            if not messages: continue
            for msg in messages:
                if msg == None: continue
                self.cb(msg, *self.args)

    def get_messages(self, buffer):
        messages = []
        while self.delimiter in buffer:
            chunks = buffer.split(self.delimiter)
            messages.extend(chunks[:-1])
            buffer = chunks[-1]
        # decode messages into strings
        messages = map(lambda x: x.decode(encoding='utf-8'), messages)
        messages = map(lambda x: json.loads(x), messages)
        return buffer, messages

import uasyncio as asyncio

class Queue:
    def __init__(self, maxsize=0):
        self._queue = []
        self._maxsize = maxsize
        self._get_event = asyncio.Event()
        self._put_event = asyncio.Event()
        self._put_event.set()  # allow immediate put if maxsize == 0

    async def put(self, item):
        while self._maxsize and len(self._queue) >= self._maxsize:
            self._put_event.clear()
            await self._put_event.wait()
        self._queue.append(item)
        self._get_event.set()

    async def get(self):
        while not self._queue:
            self._get_event.clear()
            await self._get_event.wait()
        item = self._queue.pop(0)
        if self._maxsize and len(self._queue) < self._maxsize:
            self._put_event.set()
        return item
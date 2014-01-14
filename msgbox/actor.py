import logging
import time
import threading
from Queue import Queue, Empty


logger = logging.getLogger('actor')


class Message(object):
    pass


class StopActor(Message):
    pass


class Actor(object):

    def __init__(self, name, daemon=False):
        self.thread = threading.Thread(name=name, target=self._run)
        self.thread.daemon = daemon
        self.queue = Queue()
        self.unprocessed = []

    def start(self):
        self.thread.start()

    def _run(self):
        logger.debug('actor "%s" started', self.thread.name)
        self.run()
        if self.unprocessed:
            logger.error('unprocessed msg(s): %s', self.unprocessed)
        while True:
            msg = self.receive(timeout=10)
            if msg is None:
                break

    def run(self):
        raise NotImplementedError()

    def receive(self, typ=None, block=True, timeout=None):
        msg = self._check_unprocessed(typ)
        if msg is not None:
            return msg

        if timeout is not None:
            deadline = time.time() + timeout
        left = timeout
        while left is None or left > 0:
            try:
                msg = self.queue.get(block=block, timeout=left)
            except Empty:
                return None
            if typ is None or isinstance(msg, typ):
                return msg
            else:
                self.unprocessed.append(msg)
                if timeout is not None:
                    left = deadline - time.time()

    def _check_unprocessed(self, typ):
        unprocessed = self.unprocessed
        if typ is None:
            if unprocessed:
                return unprocessed.pop(0)
        else:
            for i, msg in enumerate(unprocessed):
                if isinstance(msg, typ):
                    return unprocessed.pop(i)
        return None

    def send(self, msg):
        if not isinstance(msg, Message):
            raise ValueError('%s is not a Message instance' % msg)
        self.queue.put(msg)

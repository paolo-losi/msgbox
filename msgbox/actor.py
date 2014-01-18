import logging
import time
import threading
from Queue import Queue, Empty


logger = logging.getLogger('actor')


class Message(object):
    pass

class StopActor(Message):
    pass

class ChannelClosed(Message):
    pass

class Timeout(Message):
    pass


class RejectedMsgException(Exception):

    def __init__(self, msg):
        self.msg = msg


class Actor(object):

    def __init__(self, name, daemon=False):
        self.thread = threading.Thread(name=name, target=self._run)
        self.thread.daemon = daemon
        self.queue = Queue()
        self.unprocessed = []
        self.mutex = threading.Lock()
        self._acceptable_msgs = None

    def start(self):
        self.thread.start()

    def _run(self):
        logger.debug('actor "%s" started', self.thread.name)
        self.run()
        with self.mutex:
            self._acceptable_msgs = ()
        unprocessed = list(self.unprocessed)
        while True:
            msg = self.receive(block=False)
            if isinstance(msg, Timeout):
                break
            else:
                unprocessed.append(msg)
        if unprocessed:
            logger.error('unprocessed msg(s): %s', unprocessed)
        logger.debug('actor has quit')

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
                return Timeout()
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

    def accept_only(self, types):
        with self.mutex:
            self._acceptable_msgs = types

    def accept_all(self):
        with self.mutex:
            self._acceptable_msgs = None

    def close_channel(self):
        with self.mutex:
            self._acceptable_msgs = ()
            self.queue.put(ChannelClosed())

    def send(self, msg):
        if not isinstance(msg, Message):
            raise ValueError('%s is not a Message instance' % msg)
        with self.mutex:
            if self._acceptable_msgs is not None:
                if not isinstance(msg, self._acceptable_msgs):
                    raise RejectedMsgException(msg)
            self.queue.put(msg)

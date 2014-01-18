from __future__ import absolute_import
from collections import namedtuple

from serial.tools.list_ports import comports

from msgbox import logger
from msgbox.actor import Actor, StopActor, Timeout
from msgbox.worker import ModemWorker


SerialPortInfo = namedtuple('SerialPortInfo', ['dev', 'desc', 'hw'])


class SerialPortManager(Actor):

    def __init__(self):
        self.dev2worker = {}  # {'/dev/ttyS0': ModemHandler(), ...
        super(SerialPortManager, self).__init__('SerialPortManager')

    def remove_worker(self, worker):
        self.dev2worker.pop(worker.dev, None)
        # TODO remove the following sanity check
        for w in self.dev2worker.values():
            assert w is not worker

    def detect_serial_ports(self):
        serial_devices = set()
        for d in comports():
            dev, desc, hw = d
            if hw == 'n/a':
                continue

            serial_devices.add(dev)

            if dev not in self.dev2worker:
                spi = SerialPortInfo(desc=desc, dev=dev, hw=hw)
                mw = ModemWorker(dev=dev, serial_info=spi)
                mw.start()
                self.dev2worker[dev] = mw

        for dev in self.dev2worker.keys():
            if dev not in serial_devices:
                logger.info('stopping worker for device %s', dev)
                worker = self.dev2worker[dev]
                worker.send(StopActor())
                self.remove_worker(worker)

    def run(self):
        while True:
            self.detect_serial_ports()
            msg = self.receive(timeout=5)
            if isinstance(msg, StopActor):
                for worker in self.dev2worker.itervalues():
                    logger.info('stopping worker for device %s', worker.dev)
                    worker.send(StopActor())
                self.dev2worker = {}
                break
            elif isinstance(msg, Timeout):
                continue
            else:
                raise ValueError('unexpected msg type %s' % msg)

    def stop(self):
        self.send(StopActor())


serial_manager = SerialPortManager()

from __future__ import absolute_import
import os
import sys
from collections import namedtuple

from serial.tools.list_ports import comports

from msgbox import logger
from msgbox.actor import Actor, StopActor, Timeout
from msgbox.worker import ModemWorker
from msgbox.sim import ShutdownNotification


plat = sys.platform.lower()


SerialPortInfo = namedtuple('SerialPortInfo', ['dev', 'desc', 'hw'])


class SerialPortManager(Actor):

    def __init__(self, usb_only):
        self.usb_only = usb_only
        if usb_only and plat[:5] != 'linux':
            logger.error('--usb-only supported only on linux (ignored)')
            self.usb_only = False
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
            if self.usb_only:
                base = os.path.basename(dev)
                if (not base.startswith('ttyACM') and
                    not base.startswith('ttyUSB')):
                    continue

            serial_devices.add(dev)

            if dev not in self.dev2worker:
                spi = SerialPortInfo(desc=desc, dev=dev, hw=hw)
                mw = ModemWorker(dev=dev, serial_info=spi, serial_manager=self)
                logger.info('starting worker for device %s', dev)
                mw.start()
                self.dev2worker[dev] = mw

        for dev in self.dev2worker.keys():
            if dev not in serial_devices:
                logger.info('active worker on missing device %s', dev)

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
            elif isinstance(msg, ShutdownNotification):
                worker = msg.worker
                assert self.dev2worker[worker.dev] == worker
                self.remove_worker(worker)
                logger.info('worker for device %s has shut down', worker.dev)
            elif isinstance(msg, Timeout):
                continue
            else:
                raise ValueError('unexpected msg type %s' % msg)

    def stop(self):
        self.send(StopActor())

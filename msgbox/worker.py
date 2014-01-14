from collections import namedtuple

from gsmmodem.modem import GsmModem, TimeoutException

from msgbox import logger
from msgbox.actor import Actor, StopActor
from msgbox.sim import (sim_manager, ImsiRegister, ImsiRegistration,
                        ImsiUnregister, SimConfigChanged)


# TODO make me nicer
def sig_stren_desc(n):
    if n <= 9:
        desc = 'marginal'
    elif 9 < n <= 14:
        desc = 'workable'
    elif 14 < n <= 19:
        desc = 'good'
    else:
        desc = 'excellent'
    return '%s %s' % (n, desc)


ModemInfo = namedtuple('ModemInfo',
            ['imei', 'manufacturer', 'model', 'network', 'revision', 'signal'])


class ModemWorker(Actor):

    def __init__(self, dev, serial_info):
        self.dev = dev
        self.serial_info = serial_info
        self.modem_info = None
        self.modem = None
        self.state = 'initialized'
        self.sim_config = None
        self.imsi = None
        super(ModemWorker, self).__init__('Modem %s' % dev)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        if hasattr(self, '_state'):
            logger.info('STATE %s -> %s', self._state, new_state)
        self._state = new_state

    def run(self):
        self.modem = GsmModem(self.dev, 9600)
        step = self.connect
        try:
            while True:
                step = step()
                if step is None:
                    break
        finally:
            self.modem.close()

    def connect(self):
        self.state = 'connecting'
        while True:
            try:
                self.modem.connect()
            except TimeoutException:
                self.state = 'no modem detected'
            except Exception, e:
                self.state = 'error %s' % e
            else:
                logger.debug('found modem on %r', self.dev)
                try:
                    self.imsi, self.modem_info = self.get_modem_info()
                except Exception, e:
                    self.state = 'error %s' % e
                else:
                    return self.register
            self.modem.close()
            msg = self.receive(typ=StopActor, timeout=60)
            if isinstance(msg, StopActor):
                return None

    def register(self):
        while True:
            sim_manager.send(ImsiRegister(self))
            registration = self.receive(typ=ImsiRegistration)
            if registration.success:
                self.sim_config = registration.config
                if self.sim_config.is_startable:
                    return self.work
            else:
                return self.deactivate

            if self.sim_config.active:
                self.state = 'waiting config'
            else:
                self.state = 'stopped'
            msg = self.receive(typ=(StopActor, SimConfigChanged))
            if isinstance(msg, StopActor):
                sim_manager.send(ImsiUnregister(self))
                return None
            elif isinstance(msg, SimConfigChanged):
                return self.work

    def deactivate(self):
        elf.state = 'deactivated'
        self.receive(typ=StopActor)
        return None

    # FIXME
    work = deactivate

    def get_modem_info(self):
        modem = self.modem
        imsi = modem.imsi
        modem_info = ModemInfo(imei=modem.imei,
                               manufacturer=modem.manufacturer,
                               model=modem.model,
                               network=modem.networkName,
                               revision=modem.revision,
                               signal=sig_stren_desc(modem.signalStrength))
        return imsi, modem_info

from collections import namedtuple

from gsmmodem.modem import GsmModem, TimeoutException

from msgbox import logger
from msgbox.actor import Actor, StopActor, Timeout, ChannelClosed
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
        self.imsi = None
        self.serial_info = serial_info
        self.modem_info = None
        self.sim_config = None

        self.modem = None
        self.state = 'initialized'
        super(ModemWorker, self).__init__('Modem %s' % dev)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        if hasattr(self, '_state') and new_state != self._state:
            logger.info('STATE %s -> %s', self._state, new_state)
        self._state = new_state

    def run(self):
        step = self.connect
        try:
            while True:
                step = step()
                if step is None:
                    break
        finally:
            self._try_modem_close()

    # ~~~~~ STATES ~~~~~

    def connect(self):
        self.state = 'connecting'
        try:
            self.modem = GsmModem(self.dev, 9600)
            self.modem.connect()
        except TimeoutException:
            self.state = 'no modem detected'
        except Exception, e:
            self.state = 'error %s' % e
        else:
            logger.debug('found modem on %r', self.dev)
            try:
                self.imsi, self.modem_info = self._get_modem_info()
            except Exception, e:
                self.state = 'error %s' % e
            else:
                return self.register

        self._try_modem_close()
        msg = self.receive(typ=StopActor, timeout=5)
        if isinstance(msg, StopActor):
            return self.shutdown
        if isinstance(msg, Timeout):
            return self.connect

    def shutdown(self):
        self.state = 'shutting down'
        self.close_channel()
        if self.sim_config is not None:
            sim_manager.send(ImsiUnregister(self))
        self._try_modem_close()
        msg = self.receive()
        if isinstance(msg, ChannelClosed):
            return None
        else:
            logger.error('unexpected msg type %s', msg)
            return self.shutdown

    def register(self):
        assert self.sim_config is None
        sim_manager.send(ImsiRegister(self))
        registration = self.receive(typ=ImsiRegistration)
        if registration.success:
            self.sim_config = registration.config
            if self.sim_config.is_startable:
                return self.work
            else:
                return self.stop
        else:
            return self.deactivate

    def stop(self):
        if self.sim_config.active:
            self.state = 'waiting for config'
        else:
            self.state = 'stopped'
        msg = self.receive(typ=(StopActor, SimConfigChanged))
        if isinstance(msg, StopActor):
            return self.shutdown
        elif isinstance(msg, SimConfigChanged):
            return self.work
        elif isinstance(msg, Timeout):
            return self.register
        else:
            raise ValueError('unexpected msg type %s' % msg)

    def deactivate(self):
        self.state = 'deactivated'
        self.receive(typ=StopActor)
        return self.shutdown

    # FIXME
    work = deactivate

    # ~~~~~ utils ~~~~~

    def _get_modem_info(self):
        modem = self.modem
        imsi = modem.imsi
        modem_info = ModemInfo(imei=modem.imei,
                               manufacturer=modem.manufacturer,
                               model=modem.model,
                               network=modem.networkName,
                               revision=modem.revision,
                               signal=sig_stren_desc(modem.signalStrength))
        return imsi, modem_info

    def _try_modem_close(self):
        if self.modem is not None:
            try:
                self.modem.close()
            except Exception, e:
                logger.info('error while closing modem: %s', e)
            finally:
                self.modem = None

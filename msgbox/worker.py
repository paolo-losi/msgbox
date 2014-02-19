from collections import namedtuple

from gsmmodem.modem import (GsmModem, TimeoutException, InvalidStateException,
                            ReceivedSms, StatusReport)

from msgbox import logger
from msgbox.actor import Actor, StopActor, Timeout, ChannelClosed
from msgbox.http import http_client_manager
from msgbox.sim import (sim_manager, ImsiRegister, ImsiRegistration,
                        ImsiUnregister, SimConfigChanged, TxSmsReq, RxSmsReq,
                        ShutdownNotification)
from msgbox.util import status, cached_property


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

    def __init__(self, dev, serial_info, serial_manager):
        self.serial_manager = serial_manager
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
            self.modem = GsmModem(self.dev, 9600,
                                  smsReceivedCallbackFunc=self._rx_sms)
            self.modem.connect('6699')
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
        msg = self.receive(typ=StopActor, timeout=50)
        if isinstance(msg, StopActor):
            return self.shutdown
        if isinstance(msg, Timeout):
            return self.connect

    def shutdown(self):
        self.state = 'shutting down'
        self.close_channel()
        self._unregister()
        self._try_modem_close()
        msg = self.receive()
        if isinstance(msg, ChannelClosed):
            return None
        else:
            # FIXME there may be a queue of SMS txt requests
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
        msg = self.receive()
        if isinstance(msg, StopActor):
            return self.shutdown
        elif isinstance(msg, SimConfigChanged):
            # FIXME
            return self.work
        elif isinstance(msg, Timeout):
            return self.register
        elif isinstance(msg, TxSmsReq):
            self._send_sms_when_stopped(msg)
            return self.stop
        elif isinstance(msg, RxSmsReq):
            # FIXME enqueue somewhere?
            sms = msg.sms
            logger.error('NOT processing sms from %s %r', sms.number, sms.text)
            return self.stop
        else:
            logger.error('unexpected msg type %s', msg)
            return self.stop

    def deactivate(self):
        # FIXME is that correct to close here?
        self._try_modem_close()
        self.state = 'deactivated'
        self.receive(typ=StopActor)
        return self.shutdown

    def work(self):
        self.state = 'working'
        try:
            self.modem.processStoredSms()
        except Exception, e:
            logger.error('error while processing stored sms', exc_info=True)
            self.serial_manager.send(ShutdownNotification(self))
            return self.shutdown

        # TODO check imsi (sim hot swap)
            
        msg = self.receive(timeout=5)
        if isinstance(msg, StopActor):
            return self.shutdown
        elif isinstance(msg, SimConfigChanged):
            # FIXME
            return self.work
        elif isinstance(msg, Timeout):
            self._is_network_available
            return self.work
        elif isinstance(msg, TxSmsReq):
            self._send_sms(msg)
            return self.work
        elif isinstance(msg, RxSmsReq):
            self._process_mo_sms(msg.sms)
            return self.work
        else:
            logger.error('unexpected msg type %s', msg)


    # ~~~~~ utils ~~~~~

    def _send_sms_when_stopped(self, tx_sms):
        assert tx_sms.sender is None
        if not self.sim_config.active:
            err_msg = '%s: modem is not active' % tx_sms
            tx_sms.callback(status('ERROR', err_msg))
        else:
            self._send_sms(tx_sms)

    def _send_sms(self, tx_sms):
        # TODO handle delivery report
        if not self._is_network_available:
            err_msg = '%s: network unavailable' % tx_sms
            tx_sms.callback(status('ERROR', err_msg))
            return
        try:
            self.modem.sendSms(tx_sms.recipient, tx_sms.text)
        except Exception, e:
            logger.error('error:', exc_info=True)
            tx_sms.callback(status('ERROR', '%s: %r' % (tx_sms, e)))
        else:
            tx_sms.callback(status('OK', '%s: sms sent' % tx_sms))

    @cached_property(ttl=30)
    def _is_network_available(self):
        try:
            sig_strength = self.modem.waitForNetworkCoverage(timeout=3)
            ret = sig_strength > 0
        except (TimeoutException, InvalidStateException), e:
            ret = False
        except Exception, e:
            ret = False
        _log = logger.info if ret else logger.error
        _log('network check: available=%s', ret)
        return ret

    def _rx_sms(self, sms):
        # FIXME what if state == 'stopped'?
        if isinstance(sms, ReceivedSms):
            self.send(RxSmsReq(sms))

    def _process_mo_sms(self, sms):
        http_client_manager.enqueue(dict(
                        sender=sms.number,
                        recipient=self.sim_config.phone_number,
                        text=sms.text,
                        tstamp=sms.time,
                        url=self.sim_config.url))

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

    def _unregister(self):
        if self.sim_config is not None:
            sim_manager.send(ImsiUnregister(self))
            self.sim_config = None

    def _try_modem_close(self):
        if self.modem is not None:
            try:
                self.modem.close()
            except Exception, e:
                logger.info('error while closing modem: %s', e)
            finally:
                self.modem = None

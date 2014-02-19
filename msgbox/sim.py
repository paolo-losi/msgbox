import json
import os

from msgbox import logger
from msgbox.actor import Actor, Message, StopActor, ChannelClosed
from msgbox.util import status


DUMP_FILE = os.path.expanduser('~/.msgboxrc')


class SimConfig(object):

    def __init__(self, imsi):
        self.imsi = imsi
        self.desc = None
        self.phone_number = None
        self.url = None
        self.active = True

    @property
    def is_startable(self):
        return self.phone_number is not None and \
               self.url          is not None and \
               self.active

    @property
    def as_dict(self):
        return vars(self)

    @classmethod
    def from_dict(cls, d):
        config = cls(d.pop('imsi'))
        for k, v in d.items():
            setattr(config, k, v)
        return config


class SimConfigDB(Actor):

    def __init__(self):
        self.imsi2config = {}
        self.phone_number2config = {}
        self._load_dump()

    def update(self, imsi, desc=None, phone_number=None, url=None,
               active=None):
        assert active in (None, False, True)
        config = self._pop(imsi)

        if desc         is not None: config.desc         = desc.strip()
        if phone_number is not None: config.phone_number = phone_number.strip()
        if url          is not None: config.url          = url.strip()
        if active       is not None: config.active       = bool(active)
        self._insert(config)
        self._save_dump()

    def add(self, imsi):
        assert imsi not in self.imsi2config
        sim_config = SimConfig(imsi)
        self._insert(sim_config)
        self._save_dump()

    def route(self, phone_number):
        return self.phone_number2config.get(phone_number)

    def _load_dump(self):
        if os.path.exists(DUMP_FILE):
            with open(DUMP_FILE) as fin:
                data = json.load(fin)
                for d in data:
                    config = SimConfig.from_dict(d)
                    self._insert(config)
                logger.info('loaded config for %d sim card(s)', len(data))
        else:
            logger.info('config %s not found', DUMP_FILE)

    def _save_dump(self):
        tmp_file = DUMP_FILE + '.tmp'
        with open(tmp_file, 'w') as fout:
            configs = self.imsi2config.itervalues()
            sorted_configs = sorted(configs, key=lambda c: c.imsi)
            data = list(c.as_dict for c in sorted_configs)
            json.dump(data, fout, indent=2, sort_keys=True)
        os.rename(tmp_file, DUMP_FILE)

    def _insert(self, sim_config):
        self.imsi2config[sim_config.imsi] = sim_config
        phone_number = sim_config.phone_number
        if phone_number:
            self.phone_number2config[phone_number] = sim_config

    def _pop(self, imsi):
        sim_config = self.imsi2config.pop(imsi)
        phone_number = sim_config.phone_number
        if phone_number:
            del self.phone_number2config[phone_number]
        return sim_config

    def __getitem__(self, imsi):
        return self.imsi2config[imsi]

    def __contains__(self, imsi):
        return imsi in self.imsi2config


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class WorkerMessage(Message):

    def __init__(self, worker):
        self.worker = worker


class SimConfigChanged(Message): pass
class ImsiRegister(WorkerMessage): pass
class ImsiUnregister(WorkerMessage): pass
class ShutdownNotification(WorkerMessage): pass


class ImsiRegistration(Message):

    def __init__(self, success, config):
        self.success = success
        self.config = config


class StopSimManager(StopActor):

    def __init__(self, callback):
        self.callback = callback


class TxSmsReq(Message):

    def __init__(self, sender, recipient, text, imsi, key, callback=None):
        self.sender = sender
        self.recipient = recipient
        self.text = text
        self.imsi = imsi
        self.key = key
        self.callback = callback

    def __str__(self):
        if self.sender:
            field = 'sender "%s"' % self.sender
        else:
            field = 'imsi "%s"' % self.imsi
        return "sms tx request for %s" % field


class RxSmsReq(Message):

    def __init__(self, sms_dict):
        self.sms_dict = sms_dict


class SimManager(Actor):

    def __init__(self):
        # the same modem may show up with different serials
        # (e.g. ttyACM0 and ttyACM1). imsi2worker allow to track the
        # ModemWorker that exclusively grabs the modem.
        self.imsi2worker = {}
        self.sim_config_db = None
        self._shutting_down = False
        self._shutdown_callback = None
        super(SimManager, self).__init__('SimManager')

    def run(self):
        self.sim_config_db = SimConfigDB()

        while True:
            msg = self.receive()
            if isinstance(msg, ImsiRegister):
                self.register(msg.worker)
            elif isinstance(msg, ImsiUnregister):
                self.unregister(msg.worker)
            elif isinstance(msg, StopSimManager):
                self._shutting_down = True
                self._shutdown_callback = msg.callback
            elif isinstance(msg, TxSmsReq):
                self.route(msg)
            else:
                raise ValueError('unexpected msg type %s' % msg)

            if self._shutting_down and not self.imsi2worker:
                self.close_channel()
                return self.shutdown()

    def stop(self, callback=None):
        self.send(StopSimManager(callback))

    def shutdown(self):
        while True:
            msg = self.receive()
            if isinstance(msg, ChannelClosed):
                if self._shutdown_callback:
                    self._shutdown_callback()
                    break
            else:
                logger.error('unexpected msg %s', msg)

    def route(self, msg):
        sender = msg.sender
        imsi   = msg.imsi
        sim_config = None

        if sender:
            sim_config = self.sim_config_db.route(sender)
        if sim_config is None and imsi in self.sim_config_db:
            sim_config = self.sim_config_db[imsi]
        if sim_config is None:
            err_msg = '%s: sim not known' % msg
            if msg.callback:
                msg.callback(status('ERROR', err_msg))
            return

        worker = self.imsi2worker.get(sim_config.imsi)
        if worker:
            logger.info('%s: routing to dev %s', msg, worker.dev)
            worker.send(msg)
        else:
            msg.callback(status('ERROR', '%s: sim not found' % msg))

    def register(self, worker):
        imsi = worker.imsi
        assert imsi is not None
        if imsi in self.imsi2worker:
            if self.imsi2worker[imsi] == worker:
                success = True
            else:
                success = False
        else:
            logger.info('registered imsi "%s" -> dev "%s"', imsi, worker.dev)
            self.imsi2worker[imsi] = worker
            success = True

        if imsi not in self.sim_config_db:
            logger.info('new sim - imsi: %s', imsi)
            self.sim_config_db.add(imsi)
        config = self.sim_config_db[imsi]

        worker.send(ImsiRegistration(success, config))

    def unregister(self, worker):
        del self.imsi2worker[worker.imsi]


sim_manager = SimManager()

import json
import os

from msgbox import logger
from msgbox.actor import Actor, Message, StopActor


DUMP_FILE = os.path.expanduser('~/.msgboxrc')


class SimConfig(object):

    def __init__(self, imsi):
        self.imsi = imsi
        self.desc = ''
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
        self._load_dump()

    def _load_dump(self):
        if os.path.exists(DUMP_FILE):
            with open(DUMP_FILE) as fin:
                data = json.load(fin)
                for d in data:
                    config = SimConfig.from_dict(d)
                    self.imsi2config[config.imsi] = config
                logger.info('loaded config for %d sim card(s)', len(data))
        else:
            logger.info('config %s not found', DUMP_FILE)

    def _save_dump(self):
        tmp_file = DUMP_FILE + '.tmp'
        with open(tmp_file, 'w') as fout:
            configs = sorted((c for c in self.imsi2config.itervalues()),
                             key=lambda c: c.imsi)
            data = list(c.as_dict for c in configs)
            json.dump(data, fout, indent=2, sort_keys=True)
        os.rename(tmp_file, DUMP_FILE)

    def update(self, imsi, desc=None, phone_number=None, url=None,
               active=None):
        assert active in (None, False, True)
        sim_config = self.imsi2config[imsi]

        if desc         is not None: sim_config.desc         = desc
        if phone_number is not None: sim_config.phone_number = phone_number
        if url          is not None: sim_config.url          = url
        if active       is not None: sim_config.active       = active
        self._save_dump()

    def add(self, imsi):
        assert imsi not in self.imsi2config
        config = SimConfig(imsi)
        self.imsi2config[imsi] = config
        self._save_dump()

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

class ImsiRegistration(Message):

    def __init__(self, success, config):
        self.success = success
        self.config = config


class SimManager(Actor):

    def __init__(self):
        # the same modem may show up with different serials
        # (e.g. ttyACM0 and ttyACM1). imsi2worker allow to track the
        # ModemWorker that exclusively grabs the modem.
        self.imsi2worker = {}
        self.sim_config_db = SimConfigDB()
        self._shutting_down = False
        super(SimManager, self).__init__('SimManager')

    def run(self):
        while True:
            msg = self.receive()
            if isinstance(msg, ImsiRegister):
                self.register(msg.worker)
            elif isinstance(msg, ImsiUnregister):
                self.unregister(msg.worker)
            elif isinstance(msg, StopActor):
                self._shutting_down = True
            else:
                raise ValueError('unexpected msg type %s' % msg)
            if self._shutting_down and not self.imsi2worker:
                break

    def stop(self):
        self.send(StopActor())

    def register(self, worker):
        imsi = worker.imsi
        assert imsi is not None
        if imsi in self.imsi2worker:
            if self.imsi2worker[imsi] == worker:
                success = True
            else:
                success = False
        else:
            self.imsi2worker[imsi] = worker
            success = True

        if imsi not in self.sim_config_db:
            logger.info('new sim - imsi: %s', imsi)
            self.sim_config_db.add(imsi)
        config = self.sim_config_db[imsi]

        worker.send(ImsiRegistration(success, config))

    def unregister(self, worker):
        del self.imsi2worker[worker.imsi]

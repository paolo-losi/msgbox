from msgbox.actor import Message


class WorkerMessage(Message):

    def __init__(self, worker):
        self.worker = worker

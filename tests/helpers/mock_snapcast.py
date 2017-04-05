class MockClient(object):
    def _callback(self, data):
        pass


class MockStream(object):
    @property
    def friendly_name(self):
        return 'test stream'
    @property
    def status(self):
        return 'playing'


class MockServer(object):
    def __init__(self):
        self._clients = {'a': MockClient(), 'c': MockClient()}
        self.streams = [MockStream()]
    def stream(self, identifier):
        return MockStream()
    def group_mute(self, g, v):
        return v
    def group_clients(self, g, v):
        pass
    def client_volume(self, m, v):
        return v
    def client_name(self, m, v):
        return v
    def client_latency(self, m, v):
        return v
    def client_muted(self, m, v):
        return v

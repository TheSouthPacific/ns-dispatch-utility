"""A simple dispatch loader for testing.
"""


from nsdu import loader_api


class DispatchLoaderTest1():
    def __init__(self, config):
        self.config = config
        self.dispatch_id = {}
        self.result = ""

    def get_dispatch_config(self):
        return {'foo1': 'bar1', 'foo2': 'bar2'}

    def get_dispatch_template(self, name):
        return 'Dispatch content of {}'.format(name)

    def add_dispatch_id(self, name, dispatch_id):
        self.dispatch_id[name] = dispatch_id

    def on_update(self, name, action, result, result_time):
        self.result = {'name': name, 'action': action, 'result': result, 'result_time': result_time}

    def cleanup_loader(self):
        pass


@loader_api.dispatch_loader
def init_dispatch_loader(config):
    return DispatchLoaderTest1(config['dispatchloader-test1'])


@loader_api.dispatch_loader
def get_dispatch_config(loader):
    return loader.get_dispatch_config()


@loader_api.dispatch_loader
def get_dispatch_template(loader, name):
    return loader.get_dispatch_template(name)


@loader_api.dispatch_loader
def after_update(loader, name, action, result, result_time):
    loader.on_update(name, action, result, result_time)


@loader_api.dispatch_loader
def add_dispatch_id(loader, name, dispatch_id):
    loader.add_dispatch_id(name, dispatch_id)


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader):
    return loader.cleanup_loader()
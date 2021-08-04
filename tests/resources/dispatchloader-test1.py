"""A simple dispatch loader for testing.
"""


from nsdu import loader_api


class DispatchLoaderTest1():
    def __init__(self, config):
        self.config = config

    def get_dispatch_config(self):
        return {'foo1': 'bar1', 'foo2': 'bar2'}

    def get_dispatch_template(self, name):
        return 'Dispatch content of {}'.format(name)

    def add_dispatch_id(self, name, id):
        return

    def cleanup_loader(self):
        return


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
def add_dispatch_id(loader, name, dispatch_id):
    loader.add_dispatch_id(name, dispatch_id)
    return True


@loader_api.dispatch_loader
def cleanup_dispatch_loader(loader):
    return loader.cleanup_loader()
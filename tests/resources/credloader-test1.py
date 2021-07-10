"""A simple credential loader for testing.
"""


from nsdu import loader_api


class CredLoaderTest1():
    def __init__(self, config):
        self.config = config

    def get_creds(self):
        return {'nation1': '123456'}

    def add_cred(self, name, x_autologin):
        return True

    def remove_cred(self, name):
        return True

    def cleanup(self):
        return True


@loader_api.cred_loader
def init_cred_loader(config):
    return CredLoaderTest1(config)


@loader_api.cred_loader
def get_creds(loader):
    return loader.get_creds()


@loader_api.cred_loader
def add_cred(loader, name, x_autologin):
    return loader.add_cred(name, x_autologin)


@loader_api.cred_loader
def remove_cred(loader, name):
    return loader.remove_cred(name)


@loader_api.cred_loader
def cleanup_cred_loader(loader):
    loader.cleanup()

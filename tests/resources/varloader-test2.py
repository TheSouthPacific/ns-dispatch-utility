"""A simple variable loader for testing.
"""


from nsdu import loader_api


@loader_api.var_loader
def get_vars(config):
    return {'key2': config['varloader-test2']}

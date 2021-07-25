"""A basic simple BBCode formatter config loader for testing.
"""


from nsdu import loader_api


@loader_api.simple_bb_loader
def get_simple_bb_config(config):
    return {'key1': config['simplebbloader-test1']}

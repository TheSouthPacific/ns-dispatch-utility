"""A simple variable loader for testing.
"""


from nsdu import loader_api


@loader_api.template_var_loader
def get_template_vars(config):
    return {'key1': config['templatevarloader-test1']}

"""Information.
"""

from pathlib import Path

import appdirs


APP_NAME = 'nsdu'
AUTHOR = 'ns_tsp_usovietnam'
DESCRIPTION = 'Automatically update and format dispatches.'

DEFAULT_TEMPLATE = '[reserved]'

# Pluggy project name for loader plugins.
DISPATCH_LOADER_PROJ = 'NSDUDispatchLoader'
VAR_LOADER_PROJ = 'NSDUVarLoader'
SIMPLE_BB_LOADER_PROJ = 'NSDUSimpleBBLoader'
CRED_LOADER_PROJ = 'NSDUCredLoader'

# Default directories
default_dirs = appdirs.AppDirs(APP_NAME, AUTHOR)
CONFIG_DIR = Path(default_dirs.user_config_dir)
DATA_DIR = Path(default_dirs.user_data_dir)
LOGGING_DIR = Path(default_dirs.user_log_dir)

NSDU_PATH = Path('nsdu')

# Loader plugin directory path.
LOADER_DIR_PATH = NSDU_PATH / 'loaders'

LOADER_ENTRY_POINT_NAME = 'nationstates-nsdu'

CONFIG_ENVVAR = 'NSDU_CONFIG'
CONFIG_NAME = 'config.toml'
# Default general configuration path for copying to proper place
DEFAULT_CONFIG_PATH =  NSDU_PATH / CONFIG_NAME

# Logging configuration
LOGGING_PATH = LOGGING_DIR / 'nsdu_log.log'
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'NSDUFormatter': {
            'format': '[%(asctime)s %(name)s %(levelname)s] %(message)s'
        }
    },

    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'NSDUFormatter',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'NSDUFormatter',
            'filename': LOGGING_PATH,
            'maxBytes': 5000000,
            'backupCount': 2
        }
    },

    'root': {
        'level': 'DEBUG',
        'handlers': ['console', 'file']
    }
}

# Category name and code reference.
SUBCATEGORIES_1 = {'overview': '100',
                  'history': '101',
                  'geography': '102',
                  'culture': '103',
                  'politics': '104',
                  'legislation': '105',
                  'religion': '106',
                  'military': '107',
                  'economy': '108',
                  'international': '109',
                  'trivia': '110',
                  'miscellaneous': '111'}

SUBCATEGORIES_3 = {'policy': '305',
                   'news': '315',
                   'opinion': '325',
                   'campaign': '385'}

SUBCATEGORIES_5 = {'military': '505',
                   'trade': '515',
                   'sport': '525',
                   'drama': '535',
                   'diplomacy': '545',
                   'science': '555',
                   'culture': '565',
                   'other': '595'}

SUBCATEGORIES_8 = {'gameplay': '835',
                   'reference': '845'}

CATEGORIES = {'factbook': {'num': '1', 'subcategories': SUBCATEGORIES_1},
              'bulletin': {'num': '3', 'subcategories': SUBCATEGORIES_3},
              'account': {'num': '5', 'subcategories': SUBCATEGORIES_5},
              'meta': {'num': '8', 'subcategories': SUBCATEGORIES_8}}

import os

import toml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__),
                                   'default_config.toml')
XDG_CONFIG_HOME = os.environ.get('XDG_CONFIG_HOME',
                                 os.path.expandvars('$HOME/.config'))
CONFIG_PATH = os.path.join(XDG_CONFIG_HOME, 'i3-workspace-groups',
                           'config.toml')


class ConfigError(Exception):
    pass


# TODO: Validate config.
def get_config_with_defaults(path=CONFIG_PATH, fail_if_missing=False):
    if fail_if_missing and not os.path.exists(path):
        raise ConfigError(f'No config file found in {path}')
    config = {}
    if os.path.exists(path):
        config = toml.load(path)
    default_config = toml.load(DEFAULT_CONFIG_PATH)
    if 'renumber_workspaces' not in config:
        config['renumber_workspaces'] = default_config['renumber_workspaces']
    if 'icons' not in config:
        config['icons'] = {}
    for icon_prop in [
            'delimiter',
            'min_duplicates_count',
            'default_icon',
            'try_fallback_rules',
    ]:
        if icon_prop not in config['icons']:
            config['icons'][icon_prop] = default_config['icons'][icon_prop]
    if config['icons']['try_fallback_rules']:
        if 'rules' not in config['icons']:
            config['icons']['rules'] = []
        for rule in default_config['icons']['rules']:
            config['icons']['rules'].append(rule)
    return config

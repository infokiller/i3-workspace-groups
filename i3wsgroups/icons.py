import collections
import logging
import re
from typing import Dict

import i3ipc

logger = logging.getLogger(__name__)

WINDOW_CLASS_REGEX_STR_TO_ICON = {
    'kitty': '',
    'Termite': '',
    'URxvt': '',
    'URxvtc': '',
    'Chromium': '',
    'Chrome': '',
    'Firefox': '',
    'copyq': '',
    'Ranger': '',
    'Rofi': '',
    'Pqiv': '',
    'Pinta': '',
    '[Mm]pv': '',
    '[Vv]lc': '嗢',
    '[Ll]ibreoffice-writer': '',
    '[Ll]ibreoffice-calc': '',
    'Peek': '',
    'ipython': '',
    'python': '',
    'jupyter-qtconsole': '',
    'Gvim': '',
    'settings': '',
    'slack': '聆',
    'Zathura': '',
    'Telegram': '',
    'Pavucontrol': '墳',
}

WINDOW_CLASS_REGEX_TO_ICON = {
    re.compile(r): icon for r, icon in WINDOW_CLASS_REGEX_STR_TO_ICON.items()
}

WINDOW_INSTANCE_REGEX_STR_TO_ICON = {
    'trello': '',
    r'.*\bwhatsapp\b.*': '',
    'gmail': '',
    '[gn]vim': '',
    'file-manager': '',
    'calendar.google.com': '',
    'google drive': '',
    'ticktick': '',
}

WINDOW_INSTANCE_REGEX_TO_ICON = {
    re.compile(r): icon
    for r, icon in WINDOW_INSTANCE_REGEX_STR_TO_ICON.items()
}

# Other relevant glyphs:
#   
#            樓  
#         
#          墳 奄 奔 婢
#        
#      
#  
#       

DEFAULT_ICON = ''


def get_window_icon(window: i3ipc.Con) -> str:
    for regex, icon in WINDOW_INSTANCE_REGEX_TO_ICON.items():
        if window.window_instance and regex.match(window.window_instance):
            return icon
    for regex, icon in WINDOW_CLASS_REGEX_TO_ICON.items():
        if window.window_class and regex.match(window.window_class):
            return icon
    logger.info(
        'No icon specified for window with window class: "%s", instance: '
        '"%s", name: "%s"', window.window_class, window.window_instance,
        window.name)
    return DEFAULT_ICON


def get_workspace_icons_representation(workspace: i3ipc.Con) -> str:
    icon_to_count = collections.OrderedDict()
    for window in workspace.leaves():
        icon = get_window_icon(window)
        if icon not in icon_to_count:
            icon_to_count[icon] = 0
        icon_to_count[icon] += 1
    icons_texts = []
    for icon, count in icon_to_count.items():
        if count < 3:
            icon_text = ' '.join(icon for i in range(count))
        else:
            icon_text = '{}x{}'.format(count, icon)
        icons_texts.append(icon_text)
    return ' '.join(icons_texts)

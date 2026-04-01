from __future__ import annotations

import collections
import re
from typing import Optional

import i3ipc

from i3wsgroups.log_util import logger


class IconRule:
    def __init__(self, window_property, matcher, icon):
        # config compatible
        if window_property in ['class', 'instance', 'title']:
            window_property = "window_" + window_property

        # get from i3ipc.Con doc
        assert window_property in ["app_id", "border", "current_border_with", "floating", "focused",
                            "fullscreen_mode", "id", "layout", "name", "num", "orientation",
                            "percent", "pid", "representation", "scratchpad_state", "sticky", "type",
                            "urgent", "visible", "window", "window_class", "window_instance",
                            "window_role", "window_title"]

        self.window_property = window_property
        self.matcher = re.compile(matcher)
        self.icon = icon

    def match(self, window: i3ipc.Con) -> Optional[str]:
        property_value = getattr(window, self.window_property, None)
        # The value can be None for i3 placeholder windows and possibly others.
        if property_value and self.matcher.match(str(property_value)):
            return self.icon
        return None


class IconsResolver:

    def __init__(self, config):
        self.config = config
        self.rules = []
        for rule in self.config.get('rules', []):
            self.rules.append(IconRule(rule['property'], rule['match'], rule['icon']))

    def get_window_icon(self, window: i3ipc.Con) -> str:
        for rule in self.rules:
            icon = rule.match(window)
            if icon is not None:
                return icon

        log_string=""
        for window_property in ["app_id", "border", "current_border_with", "floating", "focused",
                                "fullscreen_mode", "id", "layout", "name", "num", "orientation",
                                "percent", "pid", "representation", "scratchpad_state", "sticky",
                                "type", "urgent", "visible", "window", "window_class",
                                "window_instance", "window_role", "window_title"]:
            property_value = getattr(window, window_property, None)
            if property_value:
                log_string += f'"{window_property}": "{property_value}", '
        if log_string.endswith(", "):
            log_string = log_string.removesuffix(", ")

        logger.info(f'No icon specified for window with {log_string}')
        return self.config['default_icon']

    def get_workspace_icons(self, workspace: i3ipc.Con) -> str:
        icon_to_count = collections.OrderedDict()
        for window in workspace.leaves():
            icon = self.get_window_icon(window)
            if icon not in icon_to_count:
                icon_to_count[icon] = 0
            icon_to_count[icon] += 1
        if not icon_to_count:
            return ''
        icons_texts = []
        delim = self.config['delimiter']
        for icon, count in icon_to_count.items():
            if count < self.config['min_duplicates_count']:
                icon_text = delim.join(icon for i in range(count))
            else:
                icon_text = f'{count}x{icon}'
            icons_texts.append(icon_text)
        prefix = self.config.get('prefix', '')
        suffix = self.config.get('suffix', '')
        return prefix + delim.join(icons_texts) + suffix

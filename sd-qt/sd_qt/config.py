from typing import List, Any

from sd_core.config import load_config_toml


default_config = """
[sd-qt]
autostart_modules = ["sd-server", "sd-watcher-afk", "sd-watcher-window"]

[sd-qt-testing]
autostart_modules = ["sd-server", "sd-watcher-afk", "sd-watcher-window"]
""".strip()


class AwQtSettings:
    def __init__(self, testing: bool):
        """
         Initialize the autostart module. This is called by __init__ and should not be called directly
         
         @param testing - Whether or not we are
        """
        config = load_config_toml("sd-qt", default_config)
        config_section: Any = config["sd-qt" if not testing else "sd-qt-testing"]

        self.autostart_modules: List[str] = config_section["autostart_modules"]

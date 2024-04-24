from sd_core.config import load_config_toml

default_config = """
[server]
hostname = "127.0.0.1"
port = "7600"

[client]
commit_interval = 10

[server-testing]
hostname = "127.0.0.1"
port = "5666"

[client-testing]
commit_interval = 5
""".strip()


def load_config():
    """
     Load configuration from TOML file. This is a wrapper around load_config_toml that allows to pass a default config to the command line.
     
     
     @return A dictionary of configuration values or None if there was no configuration to load for this client. The key is the name of the configuration value the value is the value
    """
    return load_config_toml("sd-client", default_config)

import yaml
import os
from threading import Lock

class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config = {}
        self._lock = Lock()
        self.load()

    def load(self):
        """Loads the configuration from the YAML file."""
        with self._lock:
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Config file not found at {self.config_path}")
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

    def save(self):
        """Saves the current configuration to the YAML file."""
        with self._lock:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)

    def get(self, key: str = None, default=None):
        """Retrieves a configuration value. Supports dot notation for nested keys."""
        with self._lock:
            if key is None:
                return self._config
            
            keys = key.split('.')
            value = self._config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def set(self, key: str, value):
        """Sets a configuration value. Supports dot notation for nested keys."""
        with self._lock:
            keys = key.split('.')
            target = self._config
            for k in keys[:-1]:
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value
        self.save()

    def update_system_prompt(self, new_prompt: str):
        """Helper to update the system prompt specifically."""
        self.set('clone.system_prompt', new_prompt)

# utils/config_loader.py
import os
from pathlib import Path

import yaml


class ConfigLoader:
    """配置加载器，支持多环境切换"""

    def __init__(self, env: str = None):
        # 环境优先取参数，其次取环境变量 ENV，默认 dev
        self.env = env or os.getenv("ENV", "dev")
        # 用文件自身位置定位 config/，在任何目录下启动 pytest 都不会找错路径
        self.config_dir = Path(__file__).resolve().parent.parent / "config"
        self.base_config = self._load_yaml("config.yaml")
        self.env_config = self._load_yaml(f"{self.env}.yaml")

    def _load_yaml(self, filename: str) -> dict:
        filepath = self.config_dir / filename
        with open(filepath, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get(self, key: str, default=None):
        """优先取环境配置，其次取基础配置"""
        value = self.env_config.get(key)
        return value if value is not None else self.base_config.get(key, default)

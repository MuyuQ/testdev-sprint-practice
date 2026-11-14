# fixtures/api_client.py
import requests

from utils.config_loader import ConfigLoader


class APIClient:
    """统一的 API 请求客户端：base_url、超时、请求头全在这里收敛"""

    def __init__(self, env="dev"):
        self.config = ConfigLoader(env)
        self.base_url = self.config.get("base_url")
        self.timeout = self.config.get("timeout", 10)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def request(self, method: str, endpoint: str, **kwargs):
        """统一请求入口：拼 URL、套超时；排查问题时在这里加日志"""
        url = f"{self.base_url}{endpoint}"
        return self.session.request(method, url, timeout=self.timeout, **kwargs)

    def get(self, endpoint, **kwargs):
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self.request("POST", endpoint, **kwargs)

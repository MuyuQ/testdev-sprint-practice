# tests/conftest.py
import threading

import pytest
from werkzeug.serving import make_server

from fixtures.api_client import APIClient
from server.app import app


class ServerThread:
    """在后台线程里跑 Flask：随机端口、进程退出自动停止"""

    def __init__(self, flask_app):
        # 端口传 0，由操作系统随机分配，避免本地端口冲突
        self.server = make_server("127.0.0.1", 0, flask_app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.server.port}"

    def stop(self):
        self.server.shutdown()
        self.thread.join()


@pytest.fixture(scope="session")
def base_url():
    """整个测试会话只起一次被测服务"""
    runner = ServerThread(app)
    url = runner.start()
    yield url
    runner.stop()


@pytest.fixture(scope="session")
def api_client(base_url):
    """会话级 API 客户端：把 base_url 覆盖成本会话起的服务地址"""
    client = APIClient(env="dev")
    client.base_url = base_url
    return client


@pytest.fixture(scope="function")
def auth_token(api_client):
    """每个用例独立获取 token；当前用例没用到也能当参考实现"""
    response = api_client.post(
        "/auth/login",
        json={"username": "valid_user", "password": "valid_pass"},
    )
    yield response.json()["data"]["token"]
    # 清理动作：真实项目里可在这里调用 logout 接口

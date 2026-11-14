# fixtures/device_context.py
"""端上行为上下文：把设备号 / 版本号 / 渠道包标识三个请求头注入 requests.Session，
模拟"请求来自真实 App"的端上行为。

对齐《移动端项目》收官练习：接口回归集要能模拟端上行为，也能模拟端上身份
缺失 / 被伪造，所以 fixture 同时提供"注入好的客户端"和"可定制的上下文"。
"""
import pytest

from fixtures.api_client import APIClient

# 端上身份默认值：与服务端白名单一致的合法组合
DEFAULT_DEVICE_ID = "dev-1001"
DEFAULT_APP_VERSION = "3.2.0"
DEFAULT_CHANNEL = "huawei"


class DeviceContext:
    """端上行为上下文：三个标识头，可逐项定制用于构造伪造请求"""

    def __init__(self, device_id=None, app_version=None, channel=None):
        self.device_id = device_id or DEFAULT_DEVICE_ID
        self.app_version = app_version or DEFAULT_APP_VERSION
        self.channel = channel or DEFAULT_CHANNEL

    def as_headers(self) -> dict:
        """转成请求头 dict"""
        return {
            "X-Device-Id": self.device_id,
            "X-App-Version": self.app_version,
            "X-Channel": self.channel,
        }


@pytest.fixture(scope="function")
def device_context():
    """端上行为上下文：默认合法，可定制成伪造值"""
    return DeviceContext()


@pytest.fixture(scope="function")
def device_client(api_client, base_url, device_context):
    """注入端上请求头的独立 API 客户端。

    新建客户端实例而不是改 session 级 api_client 的请求头——否则头会泄漏到
    后续所有用例（会话级共享对象的变更会跨用例存活）。
    """
    client = APIClient(env="dev")
    client.base_url = base_url
    # 端上行为注入：三个标识头进 session，之后每个请求自动携带
    client.session.headers.update(device_context.as_headers())
    return client

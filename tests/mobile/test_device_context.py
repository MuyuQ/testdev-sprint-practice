# tests/mobile/test_device_context.py
"""端上行为请求头用例：头缺失 / 伪造两类，加一条注入成功的对照组。

对齐《移动端项目》收官练习：请求头带上设备号、版本号、渠道包标识模拟端上行为；
服务端对缺失返回业务码 4001，对伪造返回业务码 4002。
"""
import pytest

from fixtures.device_context import DeviceContext
from utils.assertion_helper import assert_status_code, assert_json_field

# 合法下单报文（端上身份之外的业务参数）
VALID_ORDER_BODY = {"user_id": "user-app-1", "amount": 199}


class TestDeviceContext:
    def test_device_client_can_place_order(self, device_client):
        """对照组：注入三个端上头的客户端正常下单"""
        response = device_client.post("/app/order", json=VALID_ORDER_BODY)
        assert_status_code(response, 200)
        assert_json_field(response, "code", expected=0)
        assert_json_field(response, "data.status", expected="created")

    @pytest.mark.parametrize(
        "drop_header",
        ["X-Device-Id", "X-App-Version", "X-Channel"],
        ids=["no-device-id", "no-app-version", "no-channel"],
    )
    def test_missing_single_header_rejected(self, api_client, drop_header):
        """缺任一端上头：业务码 4001（HTTP 400）"""
        headers = DeviceContext().as_headers()
        headers.pop(drop_header)
        response = api_client.post("/app/order", json=VALID_ORDER_BODY, headers=headers)
        assert_status_code(response, 400)
        assert_json_field(response, "code", expected=4001)
        assert drop_header in response.json()["message"]

    def test_all_headers_missing_rejected(self, api_client):
        """三个端上头全缺：业务码 4001"""
        response = api_client.post("/app/order", json=VALID_ORDER_BODY)
        assert_status_code(response, 400)
        assert_json_field(response, "code", expected=4001)

    @pytest.mark.parametrize(
        "forged_kwargs,forged_part",
        [
            ({"device_id": "hack-device"}, "设备号"),
            ({"app_version": "9.9.9-fake"}, "版本号"),
            ({"channel": "pirate-market"}, "渠道"),
        ],
        ids=["forged-device-id", "forged-app-version", "forged-channel"],
    )
    def test_forged_headers_rejected(self, api_client, forged_kwargs, forged_part):
        """伪造端上身份：不在白名单 / 格式非法 → 业务码 4002（HTTP 403）"""
        headers = DeviceContext(**forged_kwargs).as_headers()
        response = api_client.post("/app/order", json=VALID_ORDER_BODY, headers=headers)
        assert_status_code(response, 403)
        assert_json_field(response, "code", expected=4002)

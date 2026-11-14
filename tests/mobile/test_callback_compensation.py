# tests/mobile/test_callback_compensation.py
"""回调丢失补偿用例：模拟回调丢失 → 触发补偿任务 → 断言补偿成功且只补一次。

对齐《移动端项目》收官练习：补回调丢失后的主动查询补偿断言。
"""
import pytest

from tests.mobile.test_device_context import VALID_ORDER_BODY
from utils.assertion_helper import assert_status_code, assert_json_field


def place_order(client):
    """下单造数：返回 order_id"""
    response = client.post("/app/order", json=VALID_ORDER_BODY)
    assert_status_code(response, 200)
    assert_json_field(response, "code", expected=0)
    return response.json()["data"]["order_id"]


def get_order(api_client, order_id):
    """查询订单当前状态"""
    response = api_client.get(f"/app/orders/{order_id}")
    assert_status_code(response, 200)
    return response.json()


@pytest.fixture()
def clean_app_state(api_client):
    """每条用例前后清空订单与审计流水：补偿扫描只看到本用例的订单"""
    api_client.post("/app/reset")
    yield
    api_client.post("/app/reset")


class TestCallbackCompensation:
    def test_lost_callback_compensated_exactly_once(self, api_client, device_client, clean_app_state):
        """回调丢失 → 补偿成功 → 重复触发补偿不再补（幂等），审计只有一条"""
        order_id = place_order(device_client)
        assert get_order(api_client, order_id)["status"] == "created"

        # 模拟回调丢失：回调在网络里丢掉，服务端没收到，订单保持未支付
        response = api_client.post(
            "/app/callback", json={"order_id": order_id, "simulate": "lost"}
        )
        assert_json_field(response, "data.received", expected=False)
        assert get_order(api_client, order_id)["status"] == "created"

        # 第一次补偿：补账成功
        response = api_client.post("/app/compensation")
        assert_status_code(response, 200)
        assert_json_field(response, "code", expected=0)
        assert_json_field(response, "data.count", expected=1)
        assert response.json()["data"]["compensated"] == [order_id]
        order = get_order(api_client, order_id)
        assert order["status"] == "paid"
        assert order["paid_via"] == "compensation"

        # 第二次补偿：已补过的不触碰 → 只补一次
        response = api_client.post("/app/compensation")
        assert_json_field(response, "data.count", expected=0)

        # 审计流水：这笔订单恰好一条补偿记录
        log = api_client.get("/app/callback-log").json()
        assert [entry for entry in log if entry["order_id"] == order_id] == [
            {"order_id": order_id, "via": "compensation"}
        ]

    def test_late_callback_after_compensation_not_double_recorded(
        self, api_client, device_client, clean_app_state
    ):
        """回调丢失 → 补账 → 回调迟到：不重复记账，账面来源仍是补偿"""
        order_id = place_order(device_client)
        api_client.post("/app/callback", json={"order_id": order_id, "simulate": "lost"})
        api_client.post("/app/compensation")

        # 迟到的回调：判重，不覆盖账面来源
        response = api_client.post("/app/callback", json={"order_id": order_id})
        assert_json_field(response, "data.received", expected=True)
        assert_json_field(response, "data.duplicate", expected=True)

        order = get_order(api_client, order_id)
        assert order["status"] == "paid"
        assert order["paid_via"] == "compensation"
        log = api_client.get("/app/callback-log").json()
        assert len([entry for entry in log if entry["order_id"] == order_id]) == 1

    def test_received_callback_not_recompensated(self, api_client, device_client, clean_app_state):
        """对照组：回调正常到达 → 已支付，补偿任务不再触碰"""
        order_id = place_order(device_client)
        response = api_client.post("/app/callback", json={"order_id": order_id})
        assert_json_field(response, "data.received", expected=True)
        assert_json_field(response, "data.duplicate", expected=False)

        assert get_order(api_client, order_id)["paid_via"] == "callback"

        response = api_client.post("/app/compensation")
        assert_json_field(response, "data.count", expected=0)
        log = api_client.get("/app/callback-log").json()
        assert [entry["via"] for entry in log if entry["order_id"] == order_id] == ["callback"]

    def test_callback_for_unknown_order_rejected(self, api_client, clean_app_state):
        """异常路径：回调指向不存在的订单 → 404 + 业务码 4003"""
        response = api_client.post("/app/callback", json={"order_id": 999999})
        assert_status_code(response, 404)
        assert_json_field(response, "code", expected=4003)

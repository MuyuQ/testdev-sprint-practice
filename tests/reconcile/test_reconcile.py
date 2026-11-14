# tests/reconcile/test_reconcile.py
"""对账差异用例：三类差异各断言"能被发现"且"归类正确"。

模式呼应《支付项目》收官练习：接口造数 → 操纵流水制造差异 → 拉两份流水比对断言。
"""
import pytest

from utils.assertion_helper import assert_status_code, assert_json_field
from utils.reconcile import (
    DIFF_AMOUNT_MISMATCH,
    DIFF_DUPLICATE,
    DIFF_UNILATERAL,
    ReconcileDiff,
)


def create_payment(api_client, order_id, amount):
    """支付造数：返回 payment_id；造数失败直接炸出明确信息"""
    response = api_client.post("/payments", json={"order_id": order_id, "amount": amount})
    assert_status_code(response, 200)
    assert_json_field(response, "code", expected=0)
    return response.json()["data"]["payment_id"]


def manipulate(api_client, side, op, payment_id, amount=None):
    """操纵流水制造脏数据"""
    payload = {"side": side, "op": op, "payment_id": payment_id}
    if amount is not None:
        payload["amount"] = amount
    return api_client.post("/reconcile/manipulate", json=payload)


def reconcile(api_client):
    """拉取两份流水并比对，返回差异报告"""
    local = api_client.get("/reconcile/local").json()
    channel = api_client.get("/reconcile/channel").json()
    return ReconcileDiff(local, channel).build()


def find_diff(report, payment_id):
    return next(d for d in report["diffs"] if d["payment_id"] == payment_id)


@pytest.fixture()
def clean_ledger(api_client):
    """每条用例前后清空流水：对账报告只含本用例造的数据"""
    api_client.post("/reconcile/reset")
    yield
    api_client.post("/reconcile/reset")


class TestReconcile:
    def test_clean_ledgers_no_diff(self, api_client, clean_ledger):
        """基线对照面：支付后不做任何操纵，三类差异均为 0"""
        payment_id = create_payment(api_client, "ORD-1", 100)

        report = reconcile(api_client)
        assert report["diffs"] == []
        assert report["summary"] == {
            DIFF_UNILATERAL: 0,
            DIFF_AMOUNT_MISMATCH: 0,
            DIFF_DUPLICATE: 0,
            "matched": 1,
            "total": 0,
        }
        assert payment_id.startswith("PAY-")

    def test_unilateral_local_has_channel_missing(self, api_client, clean_ledger):
        """单边账：本地有、渠道无 → 归类 unilateral，方向 channel_missing"""
        payment_id = create_payment(api_client, "ORD-1", 100)
        response = manipulate(api_client, "channel", "drop", payment_id)
        assert_json_field(response, "code", expected=0)

        report = reconcile(api_client)
        assert report["summary"][DIFF_UNILATERAL] == 1
        diff = find_diff(report, payment_id)
        assert diff["category"] == DIFF_UNILATERAL
        assert diff["detail"]["side"] == "channel_missing"
        assert diff["detail"]["local"]["amount"] == 100
        assert diff["detail"]["channel"] is None

    def test_amount_mismatch_detected(self, api_client, clean_ledger):
        """金额不一致：渠道侧金额被改 → 归类 amount_mismatch，detail 带两边金额"""
        payment_id = create_payment(api_client, "ORD-2", 100)
        manipulate(api_client, "channel", "bump_amount", payment_id, amount=88)

        report = reconcile(api_client)
        assert report["summary"][DIFF_AMOUNT_MISMATCH] == 1
        diff = find_diff(report, payment_id)
        assert diff["category"] == DIFF_AMOUNT_MISMATCH
        assert diff["detail"] == {"local_amount": 100, "channel_amount": 88}

    def test_duplicate_channel_entry_detected(self, api_client, clean_ledger):
        """重复入账：渠道侧同一支付记了两笔 → 归类 duplicate，笔数写入 detail"""
        payment_id = create_payment(api_client, "ORD-3", 100)
        manipulate(api_client, "channel", "duplicate", payment_id)

        report = reconcile(api_client)
        assert report["summary"][DIFF_DUPLICATE] == 1
        diff = find_diff(report, payment_id)
        assert diff["category"] == DIFF_DUPLICATE
        assert diff["detail"] == {"local_count": 1, "channel_count": 2}

    def test_all_three_diffs_coexist(self, api_client, clean_ledger):
        """三类差异同时存在：各自独立归类，互不吞没"""
        p1 = create_payment(api_client, "ORD-1", 100)  # 将变成单边账
        p2 = create_payment(api_client, "ORD-2", 200)  # 将变成金额不一致
        p3 = create_payment(api_client, "ORD-3", 300)  # 将变成重复入账
        manipulate(api_client, "channel", "drop", p1)
        manipulate(api_client, "channel", "bump_amount", p2, amount=222)
        manipulate(api_client, "channel", "duplicate", p3)

        report = reconcile(api_client)
        assert report["summary"] == {
            DIFF_UNILATERAL: 1,
            DIFF_AMOUNT_MISMATCH: 1,
            DIFF_DUPLICATE: 1,
            "matched": 0,
            "total": 3,
        }
        assert find_diff(report, p1)["category"] == DIFF_UNILATERAL
        assert find_diff(report, p2)["category"] == DIFF_AMOUNT_MISMATCH
        assert find_diff(report, p3)["category"] == DIFF_DUPLICATE

    def test_payment_missing_params(self, api_client, clean_ledger):
        """支付缺参：400"""
        response = api_client.post("/payments", json={"order_id": "ORD-X"})
        assert_status_code(response, 400)

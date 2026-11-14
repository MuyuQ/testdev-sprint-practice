# tests/order/test_order_flow.py
from utils.assertion_helper import assert_status_code, assert_json_field


class TestOrderFlow:
    """下单主流程：成功扣库存、库存不足不扣账、取消回滚、重复取消拦截"""


    def test_create_order_deducts_stock(self, api_client, goods_factory, order_factory):
        """下单成功：库存扣减，流水恰好一条 deduct 且与订单对应"""
        goods = goods_factory.create(name="下单商品", price=50, stock=10)
        order = order_factory.create(goods_id=goods["goods_id"], quantity=3)

        response = api_client.get(f"/inventory/{goods['goods_id']}")
        assert_status_code(response, 200)
        assert_json_field(response, "stock", expected=7)
        assert_json_field(response, "deducted", expected=3)

        journal = api_client.get(f"/inventory/{goods['goods_id']}/journal").json()
        assert journal == [{"op": "deduct", "order_id": order["order_id"], "quantity": 3}]

    def test_create_order_insufficient_stock(self, api_client, goods_factory):
        """库存不足：HTTP 200 + 业务码 2001，且不产生任何扣减和流水。

        网关风格接口业务失败也返回 HTTP 200，所以必须断业务码；
        失败不扣账是守恒的前提——扣了账没货就是"少卖"的成因之一。
        """
        goods = goods_factory.create(name="缺货商品", price=10, stock=2)
        response = api_client.post(
            "/orders",
            json={"user_id": "user-1", "goods_id": goods["goods_id"], "quantity": 5},
        )
        assert_status_code(response, 200)
        assert_json_field(response, "code", expected=2001)

        inventory = api_client.get(f"/inventory/{goods['goods_id']}").json()
        assert inventory["stock"] == 2
        assert inventory["deducted"] == 0
        journal = api_client.get(f"/inventory/{goods['goods_id']}/journal").json()
        assert journal == []

    def test_cancel_order_rolls_back_stock(self, api_client, goods_factory, order_factory):
        """取消订单：库存回滚，流水记 deduct + rollback 两笔且订单号一致"""
        goods = goods_factory.create(name="可取消商品", price=20, stock=5)
        order = order_factory.create(goods_id=goods["goods_id"], quantity=2)

        response = api_client.post(f"/orders/{order['order_id']}/cancel")
        assert_status_code(response, 200)
        assert_json_field(response, "code", expected=0)

        inventory = api_client.get(f"/inventory/{goods['goods_id']}").json()
        assert inventory["stock"] == 5
        assert inventory["deducted"] == 0

        journal = api_client.get(f"/inventory/{goods['goods_id']}/journal").json()
        assert [entry["op"] for entry in journal] == ["deduct", "rollback"]
        assert journal[0]["order_id"] == journal[1]["order_id"] == order["order_id"]
        assert journal[0]["quantity"] == journal[1]["quantity"] == 2

    def test_cancel_twice_rejected(self, api_client, goods_factory, order_factory):
        """重复取消：业务码 2005，库存只回滚一次，流水不出现第二条 rollback"""
        goods = goods_factory.create(name="防重复商品", price=20, stock=8)
        order = order_factory.create(goods_id=goods["goods_id"], quantity=3)

        first = api_client.post(f"/orders/{order['order_id']}/cancel")
        assert_json_field(first, "code", expected=0)
        second = api_client.post(f"/orders/{order['order_id']}/cancel")
        assert_json_field(second, "code", expected=2005)

        inventory = api_client.get(f"/inventory/{goods['goods_id']}").json()
        assert inventory["stock"] == 8
        assert inventory["deducted"] == 0
        journal = api_client.get(f"/inventory/{goods['goods_id']}/journal").json()
        assert [entry["op"] for entry in journal] == ["deduct", "rollback"]

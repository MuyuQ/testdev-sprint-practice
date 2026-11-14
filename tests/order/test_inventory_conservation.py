# tests/order/test_inventory_conservation.py
"""库存守恒断言：下单后断言 initial_stock == deducted + stock，
且库存流水与订单一一对应。

这是《电商项目》收官练习"少卖发现"的参考实现：接口逐单返回 200 并不等于
库存账对得上，守恒断言（期初 = 净扣减 + 期末）+ 流水核对能在回归里直接
暴露少扣、多扣、漏回滚这类对不上的账。
"""


class TestInventoryConservation:
    def test_conservation_after_mixed_orders(self, api_client, goods_factory, order_factory):
        """三笔下单 + 取消一笔：守恒成立，流水与订单一一对应"""
        goods = goods_factory.create(name="守恒商品", price=99, stock=7)
        orders = [
            order_factory.create(goods_id=goods["goods_id"], quantity=2),
            order_factory.create(goods_id=goods["goods_id"], quantity=1),
            order_factory.create(goods_id=goods["goods_id"], quantity=3),
        ]
        canceled = order_factory.cancel(orders[1]["order_id"])
        assert canceled.json()["code"] == 0

        inventory = api_client.get(f"/inventory/{goods['goods_id']}").json()
        # 守恒断言：期初 == 净扣减 + 当前库存（7 == (2+1+3-1) + 2）
        assert inventory["initial_stock"] == inventory["deducted"] + inventory["stock"]
        assert inventory["deducted"] == 5
        assert inventory["stock"] == 2

        journal = api_client.get(f"/inventory/{goods['goods_id']}/journal").json()
        deducts = [entry for entry in journal if entry["op"] == "deduct"]
        rollbacks = [entry for entry in journal if entry["op"] == "rollback"]
        # 每笔成功订单恰好一条 deduct，数量与订单一致
        assert {entry["order_id"] for entry in deducts} == {o["order_id"] for o in orders}
        assert sorted(entry["quantity"] for entry in deducts) == sorted(o["quantity"] for o in orders)
        # 被取消的订单恰好一条 rollback，数量与订单一致；未取消订单不出现 rollback
        assert {entry["order_id"] for entry in rollbacks} == {orders[1]["order_id"]}
        assert rollbacks[0]["quantity"] == orders[1]["quantity"]
        # 流水里不允许出现任何未知订单号
        assert {entry["order_id"] for entry in journal} <= {o["order_id"] for o in orders}

    def test_conservation_holds_when_all_orders_fail(self, api_client, goods_factory):
        """全部下单失败（库存不足）：零扣减、零流水，守恒平凡成立"""
        goods = goods_factory.create(name="缺货守恒", price=9, stock=3)
        for _ in range(3):
            response = api_client.post(
                "/orders",
                json={"user_id": "user-1", "goods_id": goods["goods_id"], "quantity": 10},
            )
            assert response.json()["code"] == 2001

        inventory = api_client.get(f"/inventory/{goods['goods_id']}").json()
        assert inventory["initial_stock"] == inventory["deducted"] + inventory["stock"]
        assert inventory["deducted"] == 0
        assert inventory["stock"] == 3
        assert api_client.get(f"/inventory/{goods['goods_id']}/journal").json() == []

    def test_multiple_goods_journal_isolated(self, api_client, goods_factory, order_factory):
        """多商品互不串账：每个 goods_id 只记自己的订单，各自守恒"""
        goods_a = goods_factory.create(name="商品A", price=10, stock=5)
        goods_b = goods_factory.create(name="商品B", price=20, stock=5)
        order_a = order_factory.create(goods_id=goods_a["goods_id"], quantity=1)
        order_b = order_factory.create(goods_id=goods_b["goods_id"], quantity=2)

        journal_a = api_client.get(f"/inventory/{goods_a['goods_id']}/journal").json()
        journal_b = api_client.get(f"/inventory/{goods_b['goods_id']}/journal").json()
        assert {entry["order_id"] for entry in journal_a} == {order_a["order_id"]}
        assert {entry["order_id"] for entry in journal_b} == {order_b["order_id"]}

        for goods_id in (goods_a["goods_id"], goods_b["goods_id"]):
            inventory = api_client.get(f"/inventory/{goods_id}").json()
            assert inventory["initial_stock"] == inventory["deducted"] + inventory["stock"]

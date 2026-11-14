# fixtures/order_factory.py
"""订单造数工厂：依赖 goods_factory，可自动现造商品或对指定商品下单；
teardown 统一回收订单（逐个取消，触发库存回滚）。
"""
import pytest


class OrderFactory:
    """通过接口下订单；goods_id 不传时自动用商品工厂现造一个"""

    def __init__(self, api_client, goods_factory):
        self.client = api_client
        self.goods_factory = goods_factory
        self.orders = []

    def create(self, quantity=1, user_id="order-factory-user", goods_id=None, goods_kwargs=None):
        """下订单，返回订单记录（含 order_id）。

        goods_kwargs 仅在 goods_id 未传时生效，透传给商品工厂
        （如 goods_kwargs={"stock": 7} 控制现造商品的库存）。
        """
        if goods_id is None:
            goods = self.goods_factory.create(**(goods_kwargs or {}))
            goods_id = goods["goods_id"]
        response = self.client.post(
            "/orders",
            json={"user_id": user_id, "goods_id": goods_id, "quantity": quantity},
        )
        body = response.json()
        assert response.status_code == 200 and body["code"] == 0, (
            f"订单造数失败：HTTP {response.status_code}，响应体 {body}"
        )
        order = {
            "order_id": body["data"]["order_id"],
            "goods_id": goods_id,
            "quantity": quantity,
            "user_id": user_id,
        }
        self.orders.append(order)
        return order

    def cancel(self, order_id):
        """取消订单：触发库存回滚，用于构造 rollback 流水"""
        return self.client.post(f"/orders/{order_id}/cancel")

    def cleanup(self):
        """teardown：回收本工厂创建的订单——逐个取消让库存回滚；
        已被用例取消过的订单重复取消返回业务码 2005，回收时忽略即可"""
        for order in self.orders:
            self.client.post(f"/orders/{order['order_id']}/cancel")
        self.orders = []


@pytest.fixture(scope="function")
def order_factory(api_client, goods_factory):
    """每条用例独立的订单工厂。

    teardown 顺序由 pytest 按 fixture 依赖 LIFO 决定：先回收订单（回滚库存），
    再删商品，保证商品删除时账面已平。
    """
    factory = OrderFactory(api_client, goods_factory)
    yield factory
    factory.cleanup()

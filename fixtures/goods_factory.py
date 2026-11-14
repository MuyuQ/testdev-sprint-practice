# fixtures/goods_factory.py
"""商品造数工厂：用例现造现用、互不依赖，teardown 统一删除自己造的商品。

呼应《电商项目》收官练习任务 2：接口造数优先，断言和清理只碰自己的数据，
避免多份用例共享写死数据导致互相踩踏。
"""
import pytest


class GoodsFactory:
    """通过接口造商品；谁造的数据归谁清理"""

    def __init__(self, api_client):
        self.client = api_client
        self.created_ids = []

    def create(self, name="测试商品", price=100, stock=10):
        """造一个商品，返回服务端数据（含 goods_id）。

        造数是前置动作，失败就直接断言炸出明确信息，不带病继续跑用例。
        """
        response = self.client.post(
            "/goods",
            json={"name": name, "price": price, "stock": stock},
        )
        body = response.json()
        assert response.status_code == 200 and body["code"] == 0, (
            f"商品造数失败：HTTP {response.status_code}，响应体 {body}"
        )
        goods_id = body["data"]["goods_id"]
        self.created_ids.append(goods_id)
        return body["data"]

    def cleanup(self):
        """teardown：逐个删除本工厂造出的商品（删除接口幂等，重复删不报错阻塞）"""
        for goods_id in self.created_ids:
            self.client.delete(f"/goods/{goods_id}")
        self.created_ids = []


@pytest.fixture(scope="function")
def goods_factory(api_client):
    """每条用例独立的商品工厂：用例结束自动清理，避免脏数据影响后续用例"""
    factory = GoodsFactory(api_client)
    yield factory
    factory.cleanup()

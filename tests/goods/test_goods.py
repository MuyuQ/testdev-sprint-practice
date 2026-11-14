# tests/goods/test_goods.py
import pytest

from utils.assertion_helper import assert_status_code, assert_json_field


class TestGoods:
    """商品接口测试：造数走 goods_factory，用例现造现用、互不依赖"""

    def test_create_goods_success(self, api_client, goods_factory):
        """创建商品：返回 goods_id，库存账初始为 期初=库存、净扣减=0"""
        goods = goods_factory.create(name="机械键盘", price=199, stock=50)

        response = api_client.get(f"/inventory/{goods['goods_id']}")
        assert_status_code(response, 200)
        assert_json_field(response, "goods_id", expected=goods["goods_id"])
        assert_json_field(response, "stock", expected=50)
        assert_json_field(response, "initial_stock", expected=50)
        assert_json_field(response, "deducted", expected=0)

    def test_create_goods_missing_fields(self, api_client):
        """创建商品：缺参返回 400"""
        response = api_client.post("/goods", json={"name": "只给了名字"})
        assert_status_code(response, 400)

    @pytest.mark.parametrize("price", [0, -1], ids=["zero-price", "negative-price"])
    def test_create_goods_invalid_price(self, api_client, price):
        """创建商品：非法价格返回 400"""
        response = api_client.post(
            "/goods", json={"name": "坏价商品", "price": price, "stock": 5}
        )
        assert_status_code(response, 400)

    def test_delete_goods_then_inventory_404(self, api_client, goods_factory):
        """删除商品后再查库存：404（工厂 teardown 会重复删，删除接口按幂等处理）"""
        goods = goods_factory.create(stock=3)
        response = api_client.delete(f"/goods/{goods['goods_id']}")
        assert_status_code(response, 200)
        assert_json_field(response, "code", expected=0)

        response = api_client.get(f"/inventory/{goods['goods_id']}")
        assert_status_code(response, 404)

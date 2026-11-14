# tests/cart/test_cart.py
from utils.assertion_helper import assert_status_code, assert_json_field


class TestCart:
    """购物车接口测试"""

    def test_add_to_cart_success(self, api_client, goods_factory):
        """加购成功：返回本次加购数量与累加后的购物车数量"""
        goods = goods_factory.create(stock=10)
        response = api_client.post(
            "/cart/items",
            json={"user_id": "user-1", "goods_id": goods["goods_id"], "quantity": 2},
        )
        assert_status_code(response, 200)
        assert_json_field(response, "code", expected=0)
        assert_json_field(response, "data.quantity", expected=2)
        assert_json_field(response, "data.cart_total", expected=2)

    def test_add_to_cart_same_goods_accumulates(self, api_client, goods_factory):
        """同一用户重复加购同一商品：数量累加"""
        goods = goods_factory.create(stock=10)
        api_client.post(
            "/cart/items",
            json={"user_id": "user-2", "goods_id": goods["goods_id"], "quantity": 1},
        )
        response = api_client.post(
            "/cart/items",
            json={"user_id": "user-2", "goods_id": goods["goods_id"], "quantity": 2},
        )
        assert_status_code(response, 200)
        assert_json_field(response, "data.cart_total", expected=3)

    def test_add_to_cart_goods_not_found(self, api_client):
        """加购不存在的商品：404 + 业务码 2002"""
        response = api_client.post(
            "/cart/items",
            json={"user_id": "user-1", "goods_id": 999999, "quantity": 1},
        )
        assert_status_code(response, 404)
        assert_json_field(response, "code", expected=2002)

    def test_add_to_cart_invalid_quantity(self, api_client, goods_factory):
        """加购数量为 0：400"""
        goods = goods_factory.create(stock=10)
        response = api_client.post(
            "/cart/items",
            json={"user_id": "user-1", "goods_id": goods["goods_id"], "quantity": 0},
        )
        assert_status_code(response, 400)

# tests/user/test_query.py
from utils.assertion_helper import assert_status_code, assert_json_field


class TestUserQuery:
    """用户查询接口测试"""

    def test_get_user_success(self, api_client):
        """查询存在的用户：200 + 姓名正确"""
        response = api_client.get("/users/1")
        assert_status_code(response, 200)
        assert_json_field(response, "data.name", expected="张三")

    def test_get_user_not_found(self, api_client):
        """查询不存在的用户：404"""
        response = api_client.get("/users/999")
        assert_status_code(response, 404)

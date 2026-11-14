# tests/user/test_login.py
import pytest

from utils.assertion_helper import assert_status_code, assert_json_field


class TestLogin:
    """登录接口测试"""

    @pytest.mark.parametrize("username,password,expected_code", [
        ("valid_user", "valid_pass", 200),    # 正常登录
        ("invalid_user", "valid_pass", 401),  # 用户不存在
        ("valid_user", "wrong_pass", 401),    # 密码错误
    ], ids=["success", "wrong-user", "wrong-pass"])
    def test_login_scenarios(self, api_client, username, password, expected_code):
        """登录接口三态：成功 / 用户不存在 / 密码错误"""
        response = api_client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        assert_status_code(response, expected_code)
        if expected_code == 200:
            assert_json_field(response, "data.token", expected_type=str)

    def test_login_missing_fields(self, api_client):
        """登录接口：缺参返回 400"""
        response = api_client.post("/auth/login", json={})
        assert_status_code(response, 400)

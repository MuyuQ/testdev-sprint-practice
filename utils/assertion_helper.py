# utils/assertion_helper.py
"""分层断言：状态码、JSON 字段分开断，失败信息直接指向问题"""


def assert_status_code(response, expected: int):
    """断言 HTTP 状态码，失败时带出响应体，方便定位"""
    assert response.status_code == expected, (
        f"状态码不符：期望 {expected}，实际 {response.status_code}，响应体：{response.text[:200]}"
    )


def assert_json_field(response, field_path: str, expected=None, expected_type=None):
    """按 a.b.c 路径断言 JSON 字段，可校验类型或具体值"""
    data = response.json()
    for key in field_path.split("."):
        assert isinstance(data, dict) and key in data, (
            f"响应缺少字段 {field_path}，实际：{data}"
        )
        data = data[key]
    if expected_type is not None:
        assert isinstance(data, expected_type), (
            f"字段 {field_path} 类型应为 {expected_type.__name__}，实际 {type(data).__name__}"
        )
    if expected is not None:
        assert data == expected, f"字段 {field_path} 期望 {expected}，实际 {data}"
    return data

# tests/permission/test_permission_matrix.py
"""权限矩阵参数化探测：YAML 矩阵每行生成一条用例。

权限配置一改、回归立刻报错——服务端策略（server 里的 ADMIN_POLICY，模拟真实
后端）与期望矩阵（config/permission-matrix.yaml）不一致时，对应组合直接红。
"""
import pytest

from fixtures.permission_matrix import load_matrix_cases
from utils.assertion_helper import assert_status_code, assert_json_field

MATRIX_CASES = load_matrix_cases()


class TestPermissionMatrix:
    @pytest.mark.parametrize(
        "role,resource,action,expected",
        MATRIX_CASES,
        ids=[
            f"{role}-{resource}-{action}-{expected}"
            for role, resource, action, expected in MATRIX_CASES
        ],
    )
    def test_permission_matrix(self, api_client, role, resource, action, expected):
        """矩阵每行一条用例：allow 期望 200，deny 期望 403"""
        response = api_client.post(
            "/admin/action",
            json={"role": role, "resource": resource, "action": action},
        )
        if expected == "allow":
            assert_status_code(response, 200)
            assert_json_field(response, "code", expected=0)
            assert_json_field(response, "data.decision", expected="allow")
        else:
            assert_status_code(response, 403)
            assert_json_field(response, "code", expected=4031)
            assert_json_field(response, "data.decision", expected="deny")

    def test_unknown_role_denied_by_default(self, api_client):
        """默认拒绝：未知角色 / 矩阵外的操作一律 403，不能放行"""
        response = api_client.post(
            "/admin/action",
            json={"role": "GHOST", "resource": "goods", "action": "delete"},
        )
        assert_status_code(response, 403)
        assert_json_field(response, "code", expected=4031)
        assert_json_field(response, "data.decision", expected="deny")

    def test_missing_params(self, api_client):
        """缺参：400"""
        response = api_client.post("/admin/action", json={"role": "ADMIN"})
        assert_status_code(response, 400)


class TestMatrixDataContract:
    """矩阵数据自身的完整性： loader 输出符合收官练习的约定"""

    def test_matrix_has_enough_combinations(self):
        """矩阵至少 12 个组合（角色 × 资源 × 操作）"""
        assert len(MATRIX_CASES) >= 12

    def test_matrix_only_contains_allow_or_deny(self):
        """期望值只有 allow / deny 两种"""
        assert {expected for *_, expected in MATRIX_CASES} == {"allow", "deny"}

    def test_matrix_covers_multiple_roles(self):
        """矩阵覆盖多个角色，避免单角色伪矩阵"""
        roles = {role for role, *_ in MATRIX_CASES}
        assert len(roles) >= 3

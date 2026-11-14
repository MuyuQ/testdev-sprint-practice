# fixtures/permission_matrix.py
"""权限矩阵加载器：把 YAML 里的角色 × 资源 × 操作矩阵拍平成参数化用例数据。

矩阵在 YAML 里按 roles -> resource -> action -> allow/deny 三层嵌套，可读性好；
用例需要的是"每行一条"，所以这里负责拍平 + 校验期望值合法性。
"""
from pathlib import Path

import yaml

# 用文件自身位置定位 config/，在任何目录下启动 pytest 都不会找错路径
MATRIX_FILE = Path(__file__).resolve().parent.parent / "config" / "permission-matrix.yaml"

ALLOWED_EXPECTED_VALUES = {"allow", "deny"}


def load_matrix_cases(matrix_path=None):
    """读取权限矩阵，拍平成 [(role, resource, action, expected), ...] 列表。

    每个元组就是一个组合；非法期望值直接抛错，不让脏数据流进用例。
    """
    path = Path(matrix_path) if matrix_path else MATRIX_FILE
    with open(path, encoding="utf-8") as f:
        matrix = yaml.safe_load(f) or {}

    cases = []
    for role, resources in (matrix.get("roles") or {}).items():
        for resource, actions in (resources or {}).items():
            for action, expected in (actions or {}).items():
                if expected not in ALLOWED_EXPECTED_VALUES:
                    raise ValueError(
                        f"权限矩阵期望值非法：{role}/{resource}/{action} = {expected!r}，"
                        f"只允许 {'/'.join(sorted(ALLOWED_EXPECTED_VALUES))}"
                    )
                cases.append((role, resource, action, expected))
    return cases

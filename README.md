# testdev-sprint-practice

[TestDev-Sprint 教学站](https://muyuq.github.io/testdev-interview-site/)《API 自动化模板》一文的收官练习参考仓库。

## 这个仓库是什么

教学站的 [practice-template/api-automation-template](https://muyuq.github.io/testdev-interview-site/practice-template/api-automation-template/) 给出了一套"拿去就能用"的接口自动化项目骨架。本仓库把文中"完整可运行示例（端到端跑通）"一节逐文件物化成真实仓库，并按教学站四个业务域项目文的收官练习，各给出一个改造示例分支：

- **main**：通用骨架。与文章的完整可运行示例一一对应，`pytest` 一条命令离线跑通。
- **ecommerce**：电商同构改造。goods / cart / order 模块 + 商品、订单造数工厂 + 库存守恒断言（"少卖"问题的参考发现手段）。对应 `project/ecommerce-project.md` 的收官练习。
- **payment**：对账模块改造。平台 / 渠道两份可操纵流水 + 三类差异（单边账、金额不一致、重复入账）的比对器与用例。对应 `project/payment-project.md` 的收官练习。
- **admin**：权限矩阵参数化探测。角色 × 资源 × 操作的期望矩阵放 YAML，`parametrize` 遍历断言 allow→200、deny→403。对应 `project/admin-platform.md` 的收官练习。
- **mobile**：App 配套接口回归集。端上行为请求头（设备号 / 版本 / 渠道）注入 + 回调丢失后的补偿任务断言。对应 `project/mobile-app-project.md` 的收官练习。

各分支互相独立，都从 main 切出。做自己的收官练习时，建议从 main 起步自己改，卡住了再来对照对应分支的参考实现。

## 目录结构（main）

```
├── config/                 # 多环境配置（config.yaml + dev.yaml / prod.yaml）
├── fixtures/               # Pytest fixtures（api_client.py 客户端封装）
├── server/                 # 本地被测服务（Flask），离线可跑
├── tests/                  # 测试用例（conftest.py 起服务 + 定义 fixtures）
│   └── user/               # 用户模块：登录、查询
├── utils/                  # 工具层（断言封装、配置加载）
├── reports/                # Allure 结果输出目录
├── pytest.ini
└── requirements.txt
```

## 运行

```bash
python -m venv .venv
source .venv/bin/activate        # Windows Git Bash；cmd 用 .venv\Scripts\activate.bat
pip install -r requirements.txt
pytest
```

预期：6 条用例全绿。`pytest.ini` 的 `addopts` 会把结果写入 `reports/allure-results`；想在浏览器里看可视化报告需另装 Java 版 Allure commandline（`allure serve reports/allure-results`），不装不影响 pytest 本身。

## 依赖

pytest、requests、PyYAML、Flask、allure-pytest。无数据库依赖：被测服务的"库存 / 流水 / 权限矩阵"等状态都放在 Flask 进程内存里，只为练习断言设计，不模拟真实存储。

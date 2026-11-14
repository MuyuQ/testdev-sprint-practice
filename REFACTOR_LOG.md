# REFACTOR_LOG：App 配套接口回归集

> 基线：main 分支的通用骨架（教学站《API 自动化模板》完整示例）。
> 本文件按"改了什么 / 为什么 / 怎么验证"记录改造点，是面试讲"项目演化"的原始素材
> （思路对齐教学站《项目故事模板》：背景 → 做法 → 结果 → 复盘）。

## 背景

把骨架改出移动端配套的接口回归集：请求头带上设备号、版本号、渠道包标识模拟端上
行为，并补回调丢失后的主动查询补偿断言。改造对齐《移动端项目》收官练习。

## 改造清单

| # | 改了什么 | 为什么 | 怎么验证 |
|---|---------|--------|---------|
| 1 | 新增 fixtures/device_context.py（DeviceContext + device_context / device_client fixture） | 端上行为收敛成上下文对象：默认合法组合一键注入 session，又能逐项定制构造伪造请求 | device_client 对照组用例正常下单 |
| 2 | tests/conftest.py 引入注册两个端上 fixture | pytest 只从 conftest 收集 fixture，fixtures/ 里的定义要进 conftest 命名空间才能被注入 | pytest 收集不报 fixture not found |
| 3 | server/app.py 新增 POST /app/order + 端上头校验 | 缺头返回业务码 4001（HTTP 400），伪造（不在版本 / 渠道白名单、设备号格式非法）返回 4002（HTTP 403） | 缺头参数化 3 例 + 全缺 1 例 + 伪造参数化 3 例 |
| 4 | server/app.py 新增 POST /app/callback（simulate=lost）与 POST /app/compensation、GET /app/callback-log、POST /app/reset | 回调丢失要可控地造（simulate=lost = 网络丢失，服务端什么都没收到）；补偿任务幂等；审计流水是"只补一次"断言的数据源 | 补偿用例组全绿 |
| 5 | 新增 tests/mobile/test_device_context.py、test_callback_compensation.py | 头缺失 / 伪造两类用例；回调丢失 → 补偿成功 → 重复补偿不二次入账 → 迟到回调判重，全链路锁死 | pytest 全绿 |

## 关键设计决策（面试可讲点）

1. **device_client 新建实例而不是改共享客户端的请求头**：api_client 是 session 级
   共享对象，直接 update 它的请求头会泄漏到后续所有用例——用例互相踩的典型来源。
   fixture 每次新建客户端再注入，隔离是白拿的。
2. **"缺"与"伪造"分开归类**：缺失是端上改造没做完（4001），伪造是身份不对
   （4002），测试分开断言才说得清被拒原因。伪造用参数化铺满三个头的伪造路径。
3. **"只补一次"断言拆成三层**：状态层（第二次补偿 count=0）、账面层（paid_via 仍是
   compensation）、审计层（callback-log 恰好一条）。只断第一层时，重复入账依然可能
   混过去——审计流水是这套断言的底气，思路对齐真实项目的幂等键 / 去重表。
4. **迟到回调判重**：补偿先到、回调后到，返回 duplicate=true 且不覆盖账面来源。
   支付回调乱序到达是常态，这条用例锁住"先到为准，后到判重"。

## 结果

`pytest` 全绿（结果数以分支实际运行为准）。user 模块 6 条基线用例保留。

## 复盘

- 端上头校验最初只查"头在不在"，伪造测试逼出了白名单设计——没有伪造用例，版本号
  校验这种逻辑根本不会出现在 mock 里。负向用例反过来推动被测对象变真实，这是
  回归集里最划算的投入。
- 补偿任务的真实实现要考虑补偿风暴（批量掉单）与补偿窗口；本练习保留"扫单 +
  幂等补账"的最小核，窗口与限流不在模板范围。

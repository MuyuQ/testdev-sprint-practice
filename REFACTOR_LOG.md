# REFACTOR_LOG：电商同构改造

> 基线：main 分支的通用骨架（教学站《API 自动化模板》完整示例）。
> 本文件按"改了什么 / 为什么 / 怎么验证"记录改造点，是面试讲"项目演化"的原始素材
> （思路对齐教学站《项目故事模板》：背景 → 做法 → 结果 → 复盘）。

## 背景

把模板里只有一个 user 模块的骨架，改成电商同构项目：goods / cart / order 三个业务
模块 + 商品、订单造数工厂 + 库存守恒断言。改造对齐《电商项目》收官练习的四步：
加业务模块、补造数工厂、加守恒断言、记录改造点。

## 改造清单

| # | 改了什么 | 为什么 | 怎么验证 |
|---|---------|--------|---------|
| 1 | server/app.py 新增 POST /goods、DELETE /goods、POST /cart/items、POST /orders、POST /orders/<id>/cancel、GET /inventory/<id>、GET /inventory/<id>/journal | 用例打真实 HTTP 接口而不是进程内 mock；DELETE 与 cancel 是造数工厂 teardown 和 rollback 流水的载体 | tests/goods、tests/cart、tests/order 全绿 |
| 2 | fixtures/api_client.py 补 delete() 方法 | 商品工厂的 teardown 要调删除接口，客户端方法与 HTTP 动词对齐 | test_delete_goods_then_inventory_404 |
| 3 | 新增 fixtures/goods_factory.py（GoodsFactory + goods_factory fixture） | 用例现造现用、互不依赖；teardown 删除只碰自己造的数据，避免共享写死数据互相踩 | 每条用例的 goods_id 都是新建的；teardown 后 /inventory 404 |
| 4 | 新增 fixtures/order_factory.py（依赖 goods_factory） | 订单造数依赖商品造数；teardown 逐个取消订单让库存回滚，与商品删除顺序由 fixture 依赖 LIFO 保证（先平账再删商品） | 每条用例结束后库存账自动回滚 |
| 5 | tests/conftest.py 引入两个工厂 fixture（import 即注册） | pytest 只从 conftest 收集 fixture，fixtures/ 目录里定义的工厂不进 conftest 命名空间就不会被用例注入——首次运行 12 条用例报 fixture not found，就是这个原因 | pytest 收集不再报 fixture not found |
| 6 | tests/order/test_inventory_conservation.py 守恒断言 | "少卖"发现手段：接口逐单返回 200 不等于账对得上；期初 = 净扣减 + 期末 + 流水与订单一一对应，能直接暴露少扣、多扣、漏回滚 | 三条守恒用例（混合下单取消 / 全部失败 / 多商品隔离）全绿 |

## 关键设计决策（面试可讲点）

1. **库存不足返回 HTTP 200 + 业务码 2001**：对齐国内网关风格——HTTP 层只反映传输
   问题，业务成败看 body 里的 code。这逼着用例做"状态码 + 业务码 + 关键字段"三层
   断言；只断状态码的用例，接口挂了照样绿。
2. **守恒断言放接口层而不是查库**：模板约定不引入数据库，用 GET /inventory 和
   journal 查询接口替代落库查询。对账思路一致：期初 = 净发生额 + 期末；真实项目里
   把这两次 GET 换成 SQL 即可平移。
3. **流水与订单一一对应**：deduct 集合 == 成功订单集合、数量逐单相等、取消订单恰
   一条 rollback、流水不允许出现未知订单号。单独"库存数字对"可能掩盖漏记流水，一
   一对应才能查出账实不符。
4. **失败不扣账**：库存不足路径不扣库存、不记流水。扣了账没出货正是"少卖"的典型
   成因，用例把这条路径的账面行为锁死。

## 结果

`pytest` 全绿（结果数以分支实际运行为准）。user 模块的 6 条基线用例保留，证明改造
没有破坏骨架。

## 复盘

- 造数工厂把"数据准备"从用例里挤出去后，用例正文只剩"动作 + 断言"，可读性明显提升；
  代价是多一层抽象，团队要约定工厂只做造数不做断言逻辑（失败快速炸出即可）。
- 守恒断言最初只校验库存数字，后来补了流水一一对应——只看数字查不出漏记流水。
  这个迭代本身就是面试里"断言怎么逐步收紧"的好素材。

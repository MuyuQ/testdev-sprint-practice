# utils/reconcile.py
"""对账差异构造器：比对本地与渠道两份流水，输出三类差异。

三类差异（canonical 定义，教学站《支付项目》收官练习引用同款分类）：
- unilateral（单边账）：一笔支付只在一侧有记录，另一侧缺失。
  参考实现侧重"本地有、渠道无"（渠道掉单）；渠道有本地无同样归入此类，
  用 detail.side 区分方向。
- amount_mismatch（金额不一致）：同一笔支付两侧都在，但金额不同。
- duplicate（重复入账）：同一笔支付在同一侧被记了多笔。

一笔支付同时命中多类时按 单边账 > 重复入账 > 金额不一致 取第一类：
先核笔数（账实是否相符），再核金额。每笔支付只出一条差异，结论唯一、
便于人工按单核对。
"""
from collections import defaultdict

DIFF_UNILATERAL = "unilateral"
DIFF_AMOUNT_MISMATCH = "amount_mismatch"
DIFF_DUPLICATE = "duplicate"


class ReconcileDiff:
    """对账差异构造器。

    用法：ReconcileDiff(local_ledger, channel_ledger).build()
    返回 {"diffs": [...], "summary": {...}}。
    """

    def __init__(self, local_ledger, channel_ledger):
        self.local_ledger = local_ledger
        self.channel_ledger = channel_ledger

    def build(self) -> dict:
        """比对两份流水，输出差异列表与按类汇总"""
        local_index = self._index(self.local_ledger)
        channel_index = self._index(self.channel_ledger)

        diffs = []
        matched = 0
        for payment_id in sorted(set(local_index) | set(channel_index)):
            category, detail = self._classify(
                local_index.get(payment_id, []),
                channel_index.get(payment_id, []),
            )
            if category is None:
                matched += 1
                continue
            diffs.append({"category": category, "payment_id": payment_id, "detail": detail})

        summary = {
            DIFF_UNILATERAL: 0,
            DIFF_AMOUNT_MISMATCH: 0,
            DIFF_DUPLICATE: 0,
            "matched": matched,
            "total": len(diffs),
        }
        for diff in diffs:
            summary[diff["category"]] += 1
        return {"diffs": diffs, "summary": summary}

    @staticmethod
    def _index(ledger) -> dict:
        """按 payment_id 聚成 entry 列表，保留重复入账的多笔记录"""
        index = defaultdict(list)
        for entry in ledger:
            index[entry["payment_id"]].append(entry)
        return dict(index)

    @staticmethod
    def _classify(local_entries, channel_entries):
        """对单笔支付归类；两侧一致时返回 (None, None)"""
        if not channel_entries:
            return DIFF_UNILATERAL, {
                "side": "channel_missing",
                "local": local_entries[0],
                "channel": None,
            }
        if not local_entries:
            return DIFF_UNILATERAL, {
                "side": "local_missing",
                "local": None,
                "channel": channel_entries[0],
            }
        if len(local_entries) > 1 or len(channel_entries) > 1:
            return DIFF_DUPLICATE, {
                "local_count": len(local_entries),
                "channel_count": len(channel_entries),
            }
        if local_entries[0]["amount"] != channel_entries[0]["amount"]:
            return DIFF_AMOUNT_MISMATCH, {
                "local_amount": local_entries[0]["amount"],
                "channel_amount": channel_entries[0]["amount"],
            }
        return None, None

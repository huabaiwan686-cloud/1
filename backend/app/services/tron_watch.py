"""USDT-TRC20 收款自动监听。

启用条件：环境变量 USDT_TRC20_ADDRESS（收款地址，无需私钥）。
原理：轮询 Trongrid 的 TRC20 转账记录，匹配待支付订单（金额 ≥ 订单金额、
到账时间 ≥ 订单创建时间），命中后自动调用 vip._activate_order 开通。

定时跑：POST /api/vip/pay/watch（可挂 cron 每 2 分钟），或部署后起后台任务。
"""
import logging
import os
from datetime import datetime

import httpx

log = logging.getLogger(__name__)

USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRONGRID = "https://api.trongrid.io"


def pay_configured() -> bool:
    return bool(os.environ.get("USDT_TRC20_ADDRESS"))


def pay_address() -> str:
    return os.environ.get("USDT_TRC20_ADDRESS", "")


def fetch_usdt_transfers(address: str, min_timestamp_ms: int, limit: int = 50) -> list[dict]:
    """查某地址收到的 USDT-TRC20 转账（按时间倒序）。"""
    params = {
        "contract_address": USDT_TRC20_CONTRACT,
        "only_to": "true",
        "limit": limit,
        "min_timestamp": min_timestamp_ms,
        "order_by": "block_timestamp,desc",
    }
    headers = {}
    api_key = os.environ.get("TRONGRID_API_KEY", "")
    if api_key:
        headers["TRON-API-KEY"] = api_key
    r = httpx.get(f"{TRONGRID}/v1/accounts/{address}/transactions/trc20",
                  params=params, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json().get("data", [])


def match_and_activate(db) -> list[str]:
    """匹配待支付订单并开通，返回命中的订单号列表。

    一笔链上转账只开一单：按 txid 去重（跨轮），同轮内已消耗的转账不再匹配。
    匹配规则：金额 ≥ 订单金额、到账时间 ≥ 订单创建时间 - 60s；金额最接近者优先。
    """
    from app.api.v1.vip import _activate_order
    from app.models.billing import VipOrder

    if not pay_configured():
        return []
    address = pay_address()
    pendings = db.query(VipOrder).filter(VipOrder.status == "pending").order_by(VipOrder.id).all()
    if not pendings:
        return []
    earliest = min(o.created_at for o in pendings if o.created_at) or datetime(2026, 1, 1)
    min_ts = int(earliest.timestamp() * 1000) - 60000
    try:
        transfers = fetch_usdt_transfers(address, min_ts, limit=200)
    except Exception as e:  # noqa: BLE001
        log.warning("trongrid query failed: %s", e)
        return []
    # 历史已用 txid（防跨轮重复消耗同一笔转账）
    used_txids = {
        r[0] for r in db.query(VipOrder.pay_txid)
        .filter(VipOrder.pay_txid.isnot(None), VipOrder.pay_txid != "").all()
    }
    hit_orders: list[str] = []
    for t in transfers:
        txid = t.get("transaction_id", "") or ""
        if not txid or txid in used_txids:
            continue
        try:
            amount = int(t.get("value", 0)) / 1_000_000
            ts = int(t.get("block_timestamp", 0))
        except (TypeError, ValueError):
            continue
        best = None
        for o in pendings:
            if o.status != "pending":
                continue
            need = float(o.amount_usdt)
            o_ts = int(o.created_at.timestamp() * 1000) if o.created_at else 0
            if amount + 1e-9 >= need and ts >= o_ts - 60000:
                if best is None or abs(amount - need) < abs(amount - float(best.amount_usdt)):
                    best = o
        if best is not None:
            best.pay_txid = txid
            _activate_order(db, best)
            hit_orders.append(best.order_no)
            used_txids.add(txid)
    return hit_orders

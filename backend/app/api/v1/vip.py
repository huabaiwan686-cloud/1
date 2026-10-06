"""VIP 会员接口：/api/vip/*。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.billing import ImageQuota, VipOrder, VipSubscription
from app.models.user import User

router = APIRouter(prefix="/vip", tags=["vip"])

PRO_PRICE_USDT = 100
PRO_DAYS = 30
PRO_MONTHLY_BG_QUOTA = 5000

PLANS = [
    {
        "id": "starter", "name": "STARTER 免费计划", "price": 0, "days": 0,
        "features": ["基础资料管理", "频道全量推送", "频道自动删除关键字", "群聊消息推送",
                     "资料管理搜索", "双向机器人", "机器人管理资料", "时间循环上架", "多账号管理"],
    },
    {
        "id": "pro", "name": "PRO WORKSPACE VIP 计划", "price": PRO_PRICE_USDT, "days": PRO_DAYS,
        "features": ["批次循环上架", "无限展示图片与随机推送", "防扫图",
                     f"每月 {PRO_MONTHLY_BG_QUOTA} 次批量替换背景额度",
                     "额度用完自动切换轻量随机扰动", "资料相似查询", "图片搜索",
                     "采集代理", "群聊关键字监听", "可联系管理员开启独立访问域名"],
    },
]


def _current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _get_or_create_quota(db: Session) -> ImageQuota:
    month = _current_month()
    q = db.query(ImageQuota).filter(ImageQuota.month == month).first()
    if not q:
        q = ImageQuota(month=month)
        db.add(q)
        db.commit()
    return q


@router.get("/plans")
def plans(user: User = Depends(get_current_user)):
    return ok(PLANS)


@router.get("/subscription")
def subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(VipSubscription).order_by(VipSubscription.id.desc()).first()
    if not sub:
        sub = VipSubscription(plan="starter")
        db.add(sub)
        db.commit()
    active = bool(sub.active_until and sub.active_until > datetime.utcnow())
    return ok({
        "plan": sub.plan if active else "starter",
        "activeUntil": sub.active_until.isoformat() if sub.active_until else None,
        "isActive": active,
    })


@router.get("/orders")
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    orders = db.query(VipOrder).order_by(VipOrder.id.desc()).all()
    return ok([{
        "id": o.id, "orderNo": o.order_no, "plan": o.plan,
        "amountUsdt": float(o.amount_usdt), "days": o.days, "status": o.status,
        "createdAt": o.created_at.isoformat() if o.created_at else None,
    } for o in orders])


@router.post("/orders")
def create_order(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.tron_watch import pay_address, pay_configured
    order_no = f"VIP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}"
    o = VipOrder(order_no=order_no, plan="pro", amount_usdt=PRO_PRICE_USDT, days=PRO_DAYS)
    db.add(o)
    db.commit()
    return ok({"id": o.id, "orderNo": o.order_no, "amountUsdt": PRO_PRICE_USDT,
               "status": "pending",
               "payAddress": pay_address() if pay_configured() else "",
               "payConfigured": pay_configured()},
              msg="订单已创建，请完成支付")


def _activate_order(db: Session, o: VipOrder) -> None:
    """订单已支付 → 开通 PRO + 发放当月额度（mark_paid 与自动监听共用）。"""
    o.status = "paid"
    o.paid_at = datetime.utcnow()
    sub = db.query(VipSubscription).order_by(VipSubscription.id.desc()).first() or VipSubscription()
    base = max(sub.active_until or datetime.utcnow(), datetime.utcnow())
    sub.plan = "pro"
    sub.active_until = base + timedelta(days=o.days)
    db.add(sub)
    q = _get_or_create_quota(db)
    q.monthly_quota = PRO_MONTHLY_BG_QUOTA
    db.commit()


@router.post("/orders/{order_id}/mark_paid")
def mark_paid(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """人工确认收款：USDT 支付网关回调/自动监听接通前使用。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    o = db.query(VipOrder).filter(VipOrder.id == order_id).first()
    if not o:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "订单不存在")
    _activate_order(db, o)
    sub = db.query(VipSubscription).order_by(VipSubscription.id.desc()).first()
    return ok(msg=f"已开通 PRO，有效期至 {sub.active_until:%Y-%m-%d}")


@router.get("/pay/info")
def pay_info(user: User = Depends(get_current_user)):
    """前端支付弹窗用：收款地址 + 金额；未配置时提示联系管理员。"""
    from app.services.tron_watch import pay_address, pay_configured
    return ok({"configured": pay_configured(), "address": pay_address(),
               "amountUsdt": PRO_PRICE_USDT, "network": "TRC20"})


@router.post("/pay/watch")
def pay_watch(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动/定时触发 TRC20 到账检查（可挂 cron 每 2 分钟）。"""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权限")
    from app.services.tron_watch import match_and_activate, pay_configured
    if not pay_configured():
        return ok({"matched": [], "msg": "未配置 USDT_TRC20_ADDRESS，仍走人工确认"})
    matched = match_and_activate(db)
    return ok({"matched": matched, "msg": f"自动开通 {len(matched)} 单"})


@router.get("/quota")
def quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """图片处理额度：背景替换余量。"""
    q = _get_or_create_quota(db)
    monthly_left = max(q.monthly_quota - q.monthly_used, 0)
    extra_left = max(q.extra_quota - q.extra_used, 0)
    return ok({
        "month": q.month,
        "monthlyQuota": q.monthly_quota, "monthlyUsed": q.monthly_used, "monthlyLeft": monthly_left,
        "extraQuota": q.extra_quota, "extraUsed": q.extra_used, "extraLeft": extra_left,
        "totalLeft": monthly_left + extra_left,
    })


def quota_available(db: Session, n: int = 1) -> bool:
    """额度预检：只查不扣。用于抠图前判断，不够则直接降级轻扰动。"""
    q = _get_or_create_quota(db)
    return (q.monthly_quota - q.monthly_used) >= n or (q.extra_quota - q.extra_used) >= n


def consume_quota(db: Session, n: int = 1) -> tuple[bool, str]:
    """扣额度：优先月度额度，再扣额外额度。返回 (是否成功, 模式)。"""
    q = _get_or_create_quota(db)
    monthly_left = q.monthly_quota - q.monthly_used
    if monthly_left >= n:
        q.monthly_used += n
        db.commit()
        return True, "quota"
    extra_left = q.extra_quota - q.extra_used
    if extra_left >= n:
        q.extra_used += n
        db.commit()
        return True, "quota"
    # 额度用完 → 自动切换轻量随机扰动（不扣费）
    return False, "light_perturb"

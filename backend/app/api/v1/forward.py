"""自动转发规则接口：/api/forward/*。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import ok
from app.core.database import get_db
from app.models.account import TgAccount
from app.models.distribution import AutoForwardRule
from app.models.user import User

router = APIRouter(prefix="/forward", tags=["forward"])


class ForwardRuleIn(BaseModel):
    name: str = ""
    account_id: int | None = None
    source_chat: str
    target_chat: str
    enabled: bool = True


def _out(r: AutoForwardRule) -> dict:
    return {
        "id": r.id, "name": r.name, "accountId": r.account_id,
        "sourceChat": r.source_chat, "targetChat": r.target_chat,
        "enabled": r.enabled,
    }


@router.get("/rules")
def list_rules(user: User = Depends(require_member), db: Session = Depends(get_db)):
    rows = db.query(AutoForwardRule).order_by(AutoForwardRule.id.desc()).all()
    return ok([_out(r) for r in rows])


@router.post("/rules")
def create_rule(body: ForwardRuleIn, user: User = Depends(require_member),
                db: Session = Depends(get_db)):
    if not body.source_chat.strip() or not body.target_chat.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "源群和目标群不能为空")
    if body.account_id:
        acc = db.query(TgAccount).filter(TgAccount.id == body.account_id).first()
        if not acc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "协议号不存在")
    r = AutoForwardRule(
        name=body.name.strip(), account_id=body.account_id,
        source_chat=body.source_chat.strip(), target_chat=body.target_chat.strip(),
        enabled=body.enabled,
    )
    db.add(r)
    db.commit()
    return ok(_out(r), msg="转发规则已创建，worker 将在 1 分钟内自动生效")


@router.put("/rules/{rule_id}/enabled")
def toggle_rule(rule_id: int, enabled: bool,
                user: User = Depends(require_member), db: Session = Depends(get_db)):
    r = db.query(AutoForwardRule).filter(AutoForwardRule.id == rule_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "规则不存在")
    r.enabled = enabled
    db.commit()
    return ok(msg="已" + ("启用" if enabled else "停用"))


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, user: User = Depends(require_member),
                 db: Session = Depends(get_db)):
    r = db.query(AutoForwardRule).filter(AutoForwardRule.id == rule_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "规则不存在")
    db.delete(r)
    db.commit()
    return ok(msg="规则已删除")

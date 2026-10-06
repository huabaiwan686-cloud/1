"""代理采集接口：/api/collect/*（规则 / 采集频道）。"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import require_member
from app.api.deps import get_current_user, ok, require_vip
from app.core.database import get_db
from app.models.content import CollectChannel, CollectRule
from app.models.user import User

router = APIRouter(prefix="/collect", tags=["collect"])


class RuleIn(BaseModel):
    name: str
    target_channels: list[int] = []
    global_apply: bool = False
    need_review: bool = True
    prefix_enabled: bool = False
    prefix_text: str = ""
    suffix_enabled: bool = False
    suffix_text: str = ""
    replace_rules: list[dict] = []
    clean_identifiers: bool = False
    fee_suffix_enabled: bool = False
    fee_suffix_text: str = ""
    delete_texts: list[str] = []
    delete_line_keywords: list[str] = []
    dedup_enabled: bool = True
    dedup_window_enabled: bool = False
    dedup_days: int = 30
    block_links: bool = True
    block_usernames: bool = True
    block_plain_text: bool = True
    block_texts: list[str] = []


class ChannelIn(BaseModel):
    name: str
    source_type: str = "account"  # account/bot/friend
    account_id: int | None = None
    source_target: str = ""
    rule_id: int | None = None
    is_active: bool = True


def _rule_out(r: CollectRule) -> dict:
    return {
        "id": r.id, "name": r.name, "targetChannels": r.target_channels,
        "globalApply": r.global_apply, "needReview": r.need_review,
        "prefixEnabled": r.prefix_enabled, "prefixText": r.prefix_text,
        "suffixEnabled": r.suffix_enabled, "suffixText": r.suffix_text,
        "replaceRules": r.replace_rules, "cleanIdentifiers": r.clean_identifiers,
        "feeSuffixEnabled": r.fee_suffix_enabled, "feeSuffixText": r.fee_suffix_text,
        "deleteTexts": r.delete_texts, "deleteLineKeywords": r.delete_line_keywords,
        "dedupEnabled": r.dedup_enabled, "dedupWindowEnabled": r.dedup_window_enabled,
        "dedupDays": r.dedup_days, "blockLinks": r.block_links,
        "blockUsernames": r.block_usernames, "blockPlainText": r.block_plain_text,
        "blockTexts": r.block_texts,
    }


@router.get("/rules")
def list_rules(user: User = Depends(require_member), db: Session = Depends(get_db)):
    return ok([_rule_out(r) for r in db.query(CollectRule).order_by(CollectRule.id.desc()).all()])


@router.post("/rules")
def create_rule(body: RuleIn, user: User = Depends(require_vip), db: Session = Depends(get_db)):
    r = CollectRule(**body.model_dump())
    db.add(r)
    db.commit()
    return ok(_rule_out(r), msg="规则已创建")


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, body: RuleIn, user: User = Depends(require_vip), db: Session = Depends(get_db)):
    r = db.query(CollectRule).filter(CollectRule.id == rule_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "规则不存在")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return ok(_rule_out(r), msg="规则已更新")


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    r = db.query(CollectRule).filter(CollectRule.id == rule_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "规则不存在")
    db.delete(r)
    db.commit()
    return ok(msg="规则已删除")


def _channel_out(c: CollectChannel) -> dict:
    return {
        "id": c.id, "name": c.name, "sourceType": c.source_type,
        "accountId": c.account_id, "sourceTarget": c.source_target,
        "ruleId": c.rule_id, "isActive": c.is_active,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/channels")
def list_channels(
    source_type: str = "", user: User = Depends(require_member), db: Session = Depends(get_db)
):
    q = db.query(CollectChannel)
    if source_type:
        q = q.filter(CollectChannel.source_type == source_type)
    return ok([_channel_out(c) for c in q.order_by(CollectChannel.id.desc()).all()])


@router.post("/channels")
def create_channel(body: ChannelIn, user: User = Depends(require_vip), db: Session = Depends(get_db)):
    c = CollectChannel(**body.model_dump())
    db.add(c)
    db.commit()
    return ok(_channel_out(c), msg="采集频道已添加")


@router.delete("/channels/{channel_id}")
def delete_channel(channel_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    c = db.query(CollectChannel).filter(CollectChannel.id == channel_id).first()
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "采集频道不存在")
    db.delete(c)
    db.commit()
    return ok(msg="已删除")

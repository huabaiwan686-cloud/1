"""群聊推送接口：/api/message/*（模板 / 计划 / 快速推送）。"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.account import TgAccount, TgDialog
from app.models.content import TaskLog
from app.models.distribution import MessageTemplate, PushPlan, QuickPushTarget
from app.models.user import User

router = APIRouter(prefix="/message", tags=["message"])


class TemplateIn(BaseModel):
    name: str = ""
    content: str = ""
    media: list[dict] = []
    enabled: bool = True


class PlanIn(BaseModel):
    account_id: int | None = None
    template_id: int | None = None
    target_groups: list[str] = []
    interval_days: int = 1
    times: list[str] = []
    multi_interval_seconds: int = 0
    enabled: bool = True


def _tpl_out(t: MessageTemplate) -> dict:
    return {
        "id": t.id, "code": t.code, "name": t.name, "content": t.content,
        "media": t.media, "enabled": t.enabled,
        "mediaCount": f"{len(t.media)}/10",
    }


@router.get("/templates")
def list_templates(keyword: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(MessageTemplate)
    if keyword:
        q = q.filter(MessageTemplate.name.contains(keyword) | MessageTemplate.content.contains(keyword))
    return ok([_tpl_out(t) for t in q.order_by(MessageTemplate.id.desc()).all()])


@router.post("/templates")
def create_template(body: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = MessageTemplate(code=f"TPL-{secrets.token_hex(4).upper()}", **body.model_dump())
    db.add(t)
    db.commit()
    return ok(_tpl_out(t), msg="模板已创建")


@router.delete("/templates/{tpl_id}")
def delete_template(tpl_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(MessageTemplate).filter(MessageTemplate.id == tpl_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    db.delete(t)
    db.commit()
    return ok(msg="模板已删除")


@router.post("/templates/{tpl_id}/push")
def push_template(tpl_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """模板推送（TODO Phase 4：接真实 TG 发送）。"""
    t = db.query(MessageTemplate).filter(MessageTemplate.id == tpl_id).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "模板不存在")
    db.add(TaskLog(action="quick_push", executor=user.username, result="processing",
                   detail=f"模板 {t.code} 推送任务已创建"))
    db.commit()
    return ok(msg="推送任务已创建")


def _plan_out(p: PushPlan) -> dict:
    return {
        "id": p.id, "accountId": p.account_id, "templateId": p.template_id,
        "targetGroups": p.target_groups, "intervalDays": p.interval_days,
        "times": p.times, "multiIntervalSeconds": p.multi_interval_seconds,
        "enabled": p.enabled,
    }


@router.get("/plans")
def list_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok([_plan_out(p) for p in db.query(PushPlan).order_by(PushPlan.id.desc()).all()])


@router.post("/plans")
def create_plan(body: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = PushPlan(**body.model_dump())
    db.add(p)
    db.commit()
    return ok(_plan_out(p), msg="推送计划已创建")


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(PushPlan).filter(PushPlan.id == plan_id).first()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "计划不存在")
    db.delete(p)
    db.commit()
    return ok(msg="计划已删除")


@router.get("/quick_targets")
def list_quick_targets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ts = db.query(QuickPushTarget).order_by(QuickPushTarget.id.desc()).all()
    return ok([{"id": t.id, "name": t.name, "target": t.target} for t in ts])


@router.post("/quick_targets")
def create_quick_target(name: str, target: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = QuickPushTarget(name=name, target=target)
    db.add(t)
    db.commit()
    return ok({"id": t.id, "name": t.name, "target": t.target}, msg="快速推送目标已创建")


class DialogRefreshIn(BaseModel):
    account_id: int


def _dialog_out(d: TgDialog) -> dict:
    return {"id": d.id, "chatId": d.chat_id, "title": d.title,
            "username": d.username, "kind": d.kind}


@router.get("/dialogs")
def list_dialogs(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """推送目标群组缓存：按协议号取上次刷新的会话列表（含缓存时间）。"""
    ds = db.query(TgDialog).filter(TgDialog.account_id == account_id).order_by(TgDialog.title).all()
    cached_at = max((d.cached_at for d in ds if d.cached_at), default=None)
    return ok({"list": [_dialog_out(d) for d in ds], "count": len(ds),
               "cachedAt": cached_at.isoformat() if cached_at else None})


@router.post("/dialogs/refresh")
async def refresh_dialogs_ep(body: DialogRefreshIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """刷新缓存：经协议号从 TG 拉取最新会话列表并全量替换缓存。"""
    a = db.query(TgAccount).filter(TgAccount.id == body.account_id).first()
    if not a or not a.phone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "TG 账号不存在")
    from app.services.tg_client import TgNotConfigured, refresh_dialogs as tg_refresh_dialogs
    try:
        dialogs = await tg_refresh_dialogs(a.phone)
    except TgNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"拉取会话失败: {e}")
    db.query(TgDialog).filter(TgDialog.account_id == a.id).delete()
    for d in dialogs:
        db.add(TgDialog(account_id=a.id, chat_id=d["chat_id"], title=d["title"],
                        username=d["username"], kind=d["kind"]))
    db.commit()
    return ok({"count": len(dialogs)}, msg=f"缓存已刷新，共 {len(dialogs)} 个会话")

"""笔记/资料库接口：/api/note/*（对齐原站）。"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.content import Note, NoteMedia, TaskLog
from app.models.user import User

router = APIRouter(prefix="/note", tags=["note"])


class NoteIn(BaseModel):
    title: str = ""
    body: str = ""
    tags: list[str] = []
    city_id: int | None = None
    account_id: int | None = None
    channel_ids: list[int] = []
    service_remark: str = ""
    scheduled_at: datetime | None = None
    media: list[dict] = []  # [{url, media_type, kind, sort_order}]


class BatchIn(BaseModel):
    ids: list[int]
    op: str  # publish/unpublish/delete/strip_number_title/find_duplicates/clear_channels/text_replace/remove_suffix/add_suffix/replace_fee_line
    params: dict = {}


def _note_out(n: Note, db: Session) -> dict:
    media = db.query(NoteMedia).filter(NoteMedia.note_id == n.id).order_by(NoteMedia.sort_order).all()
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "tags": n.tags,
        "cityId": n.city_id,
        "status": n.status,
        "source": n.source,
        "accountId": n.account_id,
        "channelIds": n.channel_ids,
        "serviceRemark": n.service_remark,
        "numberCode": n.number_code,
        "feeText": n.fee_text,
        "scheduledAt": n.scheduled_at.isoformat() if n.scheduled_at else None,
        "publishedAt": n.published_at.isoformat() if n.published_at else None,
        "createdAt": n.created_at.isoformat() if n.created_at else None,
        "media": [
            {"id": m.id, "url": m.url, "mediaType": m.media_type, "kind": m.kind, "sortOrder": m.sort_order}
            for m in media
        ],
    }


@router.get("/list")
def list_notes(
    status_: str | None = Query(None, alias="status"),
    keyword: str = "",
    tag: str = "",
    city_id: int | None = None,
    account_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Note)
    if status_ and status_ != "all":
        if status_ == "collected":
            q = q.filter(Note.source == "collect")
        elif status_ == "mine":
            q = q.filter(Note.account_id == user.id)
        else:
            q = q.filter(Note.status == status_)
    if keyword:
        q = q.filter(Note.title.contains(keyword) | Note.body.contains(keyword))
    if city_id:
        q = q.filter(Note.city_id == city_id)
    if account_id:
        q = q.filter(Note.account_id == account_id)
    total = q.count()
    notes = q.order_by(Note.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    if tag:
        notes = [n for n in notes if tag in (n.tags or [])]
    return ok({"total": total, "list": [_note_out(n, db) for n in notes]})


@router.get("/{note_id}")
def get_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    return ok(_note_out(n, db))


@router.post("/create")
def create_note(body: NoteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = Note(
        title=body.title,
        body=body.body,
        tags=body.tags,
        city_id=body.city_id,
        account_id=body.account_id,
        channel_ids=body.channel_ids,
        service_remark=body.service_remark,
        scheduled_at=body.scheduled_at,
        source="manual",
        status="draft",
    )
    db.add(n)
    db.flush()
    for i, m in enumerate(body.media):
        db.add(
            NoteMedia(
                note_id=n.id,
                url=m.get("url", ""),
                media_type=m.get("media_type", "image"),
                kind=m.get("kind", "show"),
                sort_order=m.get("sort_order", i),
            )
        )
    db.commit()
    return ok(_note_out(n, db), msg="已保存草稿")


@router.post("/{note_id}/publish")
def publish_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    n.status = "published"
    n.published_at = datetime.utcnow()
    db.add(TaskLog(note_id=n.id, action="publish", executor=user.username, result="success", detail="手动发布"))
    db.commit()
    return ok(msg="已发布")


VALID_BATCH_OPS = {
    "publish", "unpublish", "delete", "strip_number_title", "find_duplicates",
    "clear_channels", "text_replace", "remove_suffix", "add_suffix", "replace_fee_line",
}


def _apply_batch_op(notes: list[Note], op: str, params: dict, db: Session) -> dict:
    """10 项批量操作（原站 VIP 下拉）。"""
    if op not in VALID_BATCH_OPS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知操作: {op}")
    count = 0
    extra: dict = {}
    for n in notes:
        if op == "publish":
            n.status = "published"
            n.published_at = datetime.utcnow()
        elif op == "unpublish":
            n.status = "offline"
        elif op == "delete":
            db.query(NoteMedia).filter(NoteMedia.note_id == n.id).delete()
            db.delete(n)
        elif op == "strip_number_title":
            n.number_code = ""
            n.title = re.sub(r"^[#\d\s\-_]+", "", n.title).strip()
        elif op == "clear_channels":
            n.channel_ids = []
        elif op == "text_replace":
            frm, to = params.get("from", ""), params.get("to", "")
            if frm:
                n.title = n.title.replace(frm, to)
                n.body = n.body.replace(frm, to)
        elif op == "remove_suffix":
            suffix = params.get("suffix", "")
            if suffix and n.body.endswith(suffix):
                n.body = n.body[: -len(suffix)]
        elif op == "add_suffix":
            suffix = params.get("suffix", "")
            if suffix:
                n.body = (n.body or "") + suffix
        elif op == "replace_fee_line":
            lines = (n.body or "").split("\n")
            if lines:
                lines[-1] = params.get("fee_text", "")
                n.body = "\n".join(lines)
                n.fee_text = params.get("fee_text", "")
        elif op == "find_duplicates":
            continue  # 单独处理
        count += 1
    if op == "find_duplicates":
        seen: dict[str, list[int]] = {}
        for n in notes:
            key = (n.title or "").strip()
            seen.setdefault(key, []).append(n.id)
        extra["duplicates"] = {k: v for k, v in seen.items() if len(v) > 1 and k}
    db.commit()
    return {"count": count, **extra}


@router.post("/batch")
def batch_op(body: BatchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # TODO(Phase 5): VIP 鉴权——批量操作为 VIP 功能
    notes = db.query(Note).filter(Note.id.in_(body.ids)).all()
    result = _apply_batch_op(notes, body.op, body.params, db)
    db.add(
        TaskLog(
            action=f"batch_{body.op}",
            executor=user.username,
            result="success",
            detail=f"批量操作 {body.op}，{result.get('count', 0)} 条",
        )
    )
    db.commit()
    return ok(result, msg="批量操作完成")

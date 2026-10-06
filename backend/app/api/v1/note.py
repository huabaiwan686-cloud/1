"""笔记/资料库接口：/api/note/*（对齐原站）。"""
import os
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.timezone import local_to_utc_naive, utc_naive_to_local

from app.api.deps import get_current_user, ok, require_vip
from app.core.permissions import require_member
from app.core.database import get_db
from app.models.account import BotToken
from app.models.content import Note, NoteMedia, TaskLog
from app.models.distribution import Channel
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


def _note_out(n: Note, media: list[NoteMedia] | None = None, db: Session | None = None) -> dict:
    if media is None:
        media = db.query(NoteMedia).filter(NoteMedia.note_id == n.id).order_by(NoteMedia.sort_order).all() if db else []
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
        "scheduledAt": utc_naive_to_local(n.scheduled_at).isoformat() if n.scheduled_at else None,
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
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    q = db.query(Note)
    if status_ and status_ != "all":
        if status_ == "collected":
            q = q.filter(Note.source == "collect")
        elif status_ == "mine":
            q = q.filter(Note.created_by == user.id)
        else:
            q = q.filter(Note.status == status_)
    if keyword:
        q = q.filter(Note.title.contains(keyword) | Note.body.contains(keyword))
    if city_id:
        q = q.filter(Note.city_id == city_id)
    if account_id:
        q = q.filter(Note.account_id == account_id)
    total = q.count()
    if tag:
        # tags 是 JSON 数组，跨库（SQLite/PostgreSQL）统一在 Python 层过滤；
        # 先按 id 取 (id, tags) 做过滤再分页，保证 total 与列表一致
        id_tags = q.with_entities(Note.id, Note.tags).order_by(Note.id.desc()).all()
        matched_ids = [nid for nid, t in id_tags if tag in (t or [])]
        total = len(matched_ids)
        page_ids = matched_ids[(page - 1) * page_size : page * page_size]
        notes = db.query(Note).filter(Note.id.in_(page_ids)).all() if page_ids else []
        pos = {nid: i for i, nid in enumerate(page_ids)}
        notes.sort(key=lambda n: pos[n.id])
    else:
        notes = q.order_by(Note.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # 一次查出本页所有媒体，避免 N+1
    media_map: dict[int, list[NoteMedia]] = {}
    ids = [n.id for n in notes]
    if ids:
        for m in db.query(NoteMedia).filter(NoteMedia.note_id.in_(ids)).order_by(NoteMedia.sort_order).all():
            media_map.setdefault(m.note_id, []).append(m)
    return ok({"total": total, "list": [_note_out(n, media_map.get(n.id, [])) for n in notes]})


@router.get("/{note_id}")
def get_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    return ok(_note_out(n, db=db))


@router.post("/create")
def create_note(body: NoteIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    n = Note(
        title=body.title,
        body=body.body,
        tags=body.tags,
        city_id=body.city_id,
        account_id=body.account_id,
        channel_ids=body.channel_ids,
        service_remark=body.service_remark,
        # 用户填的是本地时间（Asia/Shanghai），转 UTC 入库
        scheduled_at=local_to_utc_naive(body.scheduled_at) if body.scheduled_at else None,
        source="manual",
        status="draft",
        created_by=user.id,
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
    return ok(_note_out(n, db=db), msg="已保存草稿")


@router.post("/{note_id}/publish")
def publish_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    _check_verify_video(db, n.id)  # 硬校验：必须且只能 1 个 MP4 验证视频
    n.status = "published"
    n.published_at = datetime.utcnow()
    db.add(TaskLog(note_id=n.id, action="publish", executor=user.username, result="success", detail="手动发布"))
    db.commit()
    # 定时上架：时间未到只改状态，等后台 worker 到点发送
    if n.scheduled_at and n.scheduled_at > datetime.utcnow():
        return ok(msg="已发布（定时，到点自动发送到频道）")
    sent, failed = _send_to_channels(n, user, db)
    n.scheduled_sent = True  # 立即发送成功后标记，防 worker 重复发送
    db.commit()
    if failed and not sent:
        return ok(msg=f"已发布，但发送失败：{failed[0]}")
    return ok(msg="已发布" + (f"，已发送到 {sent} 个频道" if sent else ""))


def _send_to_channels(n: Note, user: User, db: Session,
                      channel_ids: list[int] | None = None) -> tuple[list[str], list[str]]:
    """把一组上架内容真实发送到笔记绑定的频道。

    一组 =（文字+混合媒体）打包发送，紧跟一条单独验证视频。
    channel_ids：覆盖发送目标（push_all 全量推送时只发指定频道）。
    返回 (成功频道名, 失败原因)。
    """
    from app.api.v1.bots import _dec
    from app.api.v1.media import get_matting_global
    from app.services.publisher import _media_bytes, matt_for_publish, send_listing_set

    media = db.query(NoteMedia).filter(NoteMedia.note_id == n.id).order_by(NoteMedia.sort_order).all()
    show = [{"url": m.url, "media_type": m.media_type} for m in media if m.kind == "show"]
    verify = [{"url": m.url} for m in media if m.kind == "verify"]

    # 全局抠图模式：开启后所有发往频道的展示图按所选背景自动抠图（内存处理，不落盘）；
    # 服务器只保留原图，每次循环都拿原图重新处理再发送
    gm = get_matting_global(db)
    if gm:
        processed = []
        for m in show:
            try:
                fname, data = _media_bytes(m["url"])
                data = matt_for_publish(data, gm["bg_data"], db, user)
                processed.append({"data": data, "name": fname})
            except Exception:  # noqa: BLE001  单张失败用原图，不中断整组
                processed.append(m)
        show = processed

    sent, failed = [], []
    cids = channel_ids if channel_ids is not None else (n.channel_ids or [])
    for cid in cids:
        ch = db.query(Channel).filter(Channel.id == cid).first()
        if not ch:
            failed.append(f"频道#{cid}：频道不存在（可能已被删除）")
            continue
        if not ch.is_active:
            continue
        chat = ch.tg_channel_id or ch.username
        if not chat:
            failed.append(f"{ch.name}：未配置频道地址")
            continue
        if not ch.bot_id:
            failed.append(f"{ch.name}：未绑定推送 Bot")
            continue
        bot = db.query(BotToken).filter(BotToken.id == ch.bot_id).first()
        if not bot:
            failed.append(f"{ch.name}：推送 Bot 不存在")
            continue
        # 分步幂等：读已有进度，断点续发（相册成功/视频失败时只重发视频）
        progress = dict(n.send_progress or {})
        ch_progress = dict(progress.get(str(cid), {}))

        def _mark_step(step: str):
            ch_progress[step] = True
            progress[str(cid)] = ch_progress
            n.send_progress = dict(progress)
            db.flush()  # 每步成功立即持久化，崩溃后可续

        # 循环重发变体：该频道开变体开关 且 之前成功发过（非首次）→ 做无意义微调防 TG 判重
        use_variation = bool(getattr(ch, "variation_enabled", True)) and db.query(TaskLog).filter(
            TaskLog.note_id == n.id, TaskLog.action == "push_send",
            TaskLog.result == "success",
            TaskLog.detail.contains(ch.name)).first() is not None
        try:
            res = send_listing_set(
                _dec(bot.token_secret), chat,
                title=n.title, body=n.body, tags=n.tags,
                show_media=show, verify_media=verify,
                # 全局抠图已处理则不再叠加频道防扫图
                anti_scan_mode="original" if gm else (ch.anti_scan_mode or "original"),
                resume=ch_progress, on_step=_mark_step,
                variation=use_variation,
            )
            detail = f"已发送到 {ch.name}（{chat}）：{res}"
            db.add(TaskLog(note_id=n.id, action="push_send", executor=user.username,
                           result="success", detail=detail))
            # 记录发送回执（message_id），用于下架自动删帖
            from app.models.content import PublishReceipt
            for mid in (res.get("message_ids") or []):
                if mid:
                    db.add(PublishReceipt(note_id=n.id, channel_id=cid, bot_id=ch.bot_id,
                                          chat_id=str(chat), message_id=mid, part="ordinary"))
            if res.get("video_message_id"):
                db.add(PublishReceipt(note_id=n.id, channel_id=cid, bot_id=ch.bot_id,
                                      chat_id=str(chat), message_id=res["video_message_id"], part="video"))
            sent.append(ch.name)
        except Exception as e:  # noqa: BLE001
            detail = f"{ch.name} 发送失败：{e}"
            db.add(TaskLog(note_id=n.id, action="push_send", executor=user.username,
                           result="failed", detail=detail))
            failed.append(detail)
    if not failed:
        n.send_progress = {}  # 全部频道发送完成，清空断点进度
        db.flush()
    return sent, failed


def _check_verify_video(db, note_id: int):
    """发布前硬校验：验证视频必须且只能是 1 个 MP4，否则拒绝发布。"""
    from app.models.content import NoteMedia
    videos = db.query(NoteMedia).filter(
        NoteMedia.note_id == note_id, NoteMedia.kind == "verify").all()
    if len(videos) != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"验证视频必须且只能是 1 个（当前 {len(videos)} 个）")
    v = videos[0]
    url = (v.url or "").lower()
    if not url.endswith(".mp4"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证视频必须是 MP4 格式")


def _queue_removal(db, note_id: int):
    """资料下架时入删帖队列：有未删回执且无进行中任务才入队。"""
    from app.models.content import PublishReceipt, RemovalQueue
    has_receipts = db.query(PublishReceipt).filter(
        PublishReceipt.note_id == note_id, PublishReceipt.deleted.is_(False)).first()
    if not has_receipts:
        return
    running = db.query(RemovalQueue).filter(
        RemovalQueue.note_id == note_id,
        RemovalQueue.status.in_(["queued", "running"])).first()
    if running:
        return
    upto = db.query(PublishReceipt.id).filter(
        PublishReceipt.note_id == note_id).order_by(PublishReceipt.id.desc()).first()
    db.add(RemovalQueue(note_id=note_id, upto=upto[0] if upto else 0))
    db.flush()


def _review_note(note_id: int, approve: bool, user: User, db: Session):
    """正式审核：通过 → published；拒绝 → offline（可恢复，非删除）。"""
    n = db.query(Note).filter(Note.id == note_id).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    if approve:
        _check_verify_video(db, n.id)  # 硬校验：必须且只能 1 个 MP4 验证视频
        n.status = "published"
        n.published_at = datetime.utcnow()
        action, detail, msg = "review_approve", "审核通过并发布", "审核通过，已发布"
        if not (n.scheduled_at and n.scheduled_at > datetime.utcnow()):
            sent, failed = _send_to_channels(n, user, db)
            n.scheduled_sent = True  # 防 worker 重复发送
            if failed and not sent:
                msg = f"审核通过，但发送失败：{failed[0]}"
    else:
        n.status = "offline"
        _queue_removal(db, n.id)  # 下架自动删帖
        action, detail, msg = "review_reject", "审核拒绝（下架，可恢复）", "已拒绝（移入下架）"
    db.add(TaskLog(note_id=n.id, action=action, executor=user.username, result="success", detail=detail))
    db.commit()
    return ok(msg=msg)


@router.post("/{note_id}/approve")
def approve_note(note_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    return _review_note(note_id, True, user, db)


@router.post("/{note_id}/reject")
def reject_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _review_note(note_id, False, user, db)


VALID_BATCH_OPS = {
    "publish", "unpublish", "delete", "strip_number_title", "find_duplicates",
    "clear_channels", "text_replace", "remove_suffix", "add_suffix", "replace_fee_line",
}


def _apply_batch_op(notes: list[Note], op: str, params: dict, db: Session, user: User | None = None) -> dict:
    """10 项批量操作（原站 VIP 下拉）。publish 会真实发送到绑定频道（一组=文字+媒体打包，紧跟验证视频）。"""
    if op not in VALID_BATCH_OPS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知操作: {op}")
    count = 0
    extra: dict = {}
    for n in notes:
        if op == "publish":
            n.status = "published"
            n.published_at = datetime.utcnow()
            if user is not None and not (n.scheduled_at and n.scheduled_at > datetime.utcnow()):
                _send_to_channels(n, user, db)
                n.scheduled_sent = True  # 防 worker 重复发送
        elif op == "unpublish":
            n.status = "offline"
            _queue_removal(db, n.id)
        elif op == "delete":
            # 同步删磁盘文件（与素材删除一致），避免 uploads 残留
            from app.api.v1.media import _fs_path
            for m in db.query(NoteMedia).filter(NoteMedia.note_id == n.id).all():
                try:
                    fp = _fs_path(m.url)
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception:
                    pass
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
    # 普通用户仅允许批量上下架，其他批量操作需要会员
    if body.op not in ("publish", "unpublish") and not (user.is_admin or user.is_member):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该功能仅会员可用，请先开通会员")
    notes = db.query(Note).filter(Note.id.in_(body.ids)).all()
    result = _apply_batch_op(notes, body.op, body.params, db, user)
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

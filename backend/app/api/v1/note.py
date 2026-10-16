"""笔记/资料库接口：/api/note/*（对齐原站）。"""
import os
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.timezone import local_to_utc_naive, utc_naive_to_local

from app.api.deps import get_current_user, ok
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
    # tags 必须返回数组：防双重编码字符串（Note 25 曾是 '"[]"' 字符串，前端 .join 报错）
    _tags = n.tags
    if isinstance(_tags, str):
        try:
            import json as _json
            _tags = _json.loads(_tags)
        except Exception:
            _tags = []
    if not isinstance(_tags, list):
        _tags = []
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "tags": _tags,
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
    channel_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    q = db.query(Note)
    # 数据隔离：所有用户（包括超管）只能看到自己的笔记
    q = q
    if channel_id:
        # 按频道筛选：笔记的 channel_ids 包含该频道
        # channel_ids 是 JSON 列存 int 数组，用 Python 层精确匹配（避免 SQLite contains 子串误匹配）
        _all_ids = [n.id for n in q.all() if channel_id in (n.channel_ids or [])]
        q = q.filter(Note.id.in_(_all_ids)) if _all_ids else q.filter(Note.id == -1)
    if status_ and status_ != "all":
        if status_ == "collected":
            q = q.filter(Note.source == "collect")
        elif status_ == "mine":
            pass  # 已按用户过滤
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
    n = db.query(Note).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    return ok(_note_out(n, db=db))


@router.post("/create")
def create_note(body: NoteIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    # 校验 channel_ids 归属（不能用他人频道）
    if body.channel_ids:
        from app.models.distribution import Channel as _Ch
        _valid = db.query(_Ch).filter(_Ch.id.in_(body.channel_ids), _Ch.created_by == user.id).all()
        if len(_valid) != len(body.channel_ids):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "频道 ID 包含不属于你的频道")
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


class NoteUpdateIn(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None


@router.put("/{note_id}")
def update_note(note_id: int, body: NoteUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """编辑笔记标题/正文/标签（仅自己的笔记；已发布笔记仅改库内文案，不重发 TG）。"""
    n = db.query(Note).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    if body.title is not None:
        n.title = body.title
    if body.body is not None:
        n.body = body.body
    if body.tags is not None:
        n.tags = body.tags
    db.commit()
    return ok(_note_out(n, db=db), msg="已保存")


@router.post("/{note_id}/unpublish")
def unpublish_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """单条下架：Telegram 确认删帖后才翻 offline；删除失败不报成功，状态保持已发布可重试。"""
    n = db.query(Note).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    if n.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"当前状态为[{n.status}]，只有已发布的内容可以下架")

    handled, errors = _delete_note_receipts_sync(db, n.id)
    if errors:
        db.add(TaskLog(note_id=n.id, action="unpublish", executor=user.username, result="failed",
                       detail=f"下架失败：{len(errors)} 条 Telegram 消息删除失败：{'; '.join(errors[:3])}"))
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            f"下架失败：{len(errors)} 条 Telegram 消息删除失败，状态保持已发布：{'; '.join(errors[:3])}")
    n.status = "offline"
    # 下架 → 停止循环（循环任务只是记录，跟全局循环走；下架了就停，重新上架自动开启）
    from app.models.content import LoopTask as _LT
    _lt = db.query(_LT).filter(_LT.note_id == n.id, _LT.enabled.is_(True)).all()
    for _t in _lt:
        _t.enabled = False
    db.add(TaskLog(note_id=n.id, action="unpublish", executor=user.username, result="success",
                   detail=f"单条下架成功，Telegram 确认删除 {handled} 条消息"))
    db.commit()
    return ok(msg=f"已下架（Telegram 已确认删除 {handled} 条消息）" if handled else "已下架（无待删除的 Telegram 消息）")


@router.post("/{note_id}/publish")
def publish_note(note_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Note).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    _check_verify_video(db, n.id)  # 硬校验：必须且只能 1 个 MP4 验证视频
    # 定时上架：时间未到只改状态，等后台 worker 到点发送
    if n.scheduled_at and n.scheduled_at > datetime.utcnow():
        n.status = "published"
        n.published_at = datetime.utcnow()
        db.add(TaskLog(note_id=n.id, action="publish", executor=user.username, result="success", detail="定时发布（到点自动发送）"))
        _auto_create_loop_task(db, n, user)  # 网站上传自动进循环（和投稿机器人同逻辑）
        db.commit()
        return ok(msg="已发布（定时，到点自动发送到频道）")
    # 立即发送：先实际发送到 Telegram，成功后才标记状态
    sent, failed = _send_to_channels(n, user, db)
    n.scheduled_sent = True
    if failed and not sent:
        # 全部失败：标记为失败，保存错误详情
        n.status = "publish_failed"
        db.add(TaskLog(note_id=n.id, action="publish", executor=user.username, result="fail",
                       detail=f"Telegram 发送失败：{failed[0]}"))
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Telegram 发布失败：{failed[0]}")
    # 至少部分成功
    n.status = "published"
    n.published_at = datetime.utcnow()
    db.add(TaskLog(note_id=n.id, action="publish", executor=user.username, result="success",
                   detail=f"手动发布，已发送到 {len(sent)} 个频道" + (f"；{len(failed)} 个失败：{failed[0]}" if failed else "")))
    _auto_create_loop_task(db, n, user)  # 网站上传自动进循环（和投稿机器人同逻辑）
    db.commit()
    return ok(msg="已发布" + (f"，已发送到 {len(sent)} 个频道" if sent else "") + (f"（{len(failed)} 个频道失败）" if failed else ""))


def _auto_create_loop_task(db, n, user):
    """网站上传自动进循环（和投稿机器人同逻辑，用户要求统一）。

    投稿机器人和网站上传只是上传方式不同，最终都要到网站资料库、自动进循环。
    之前 bug：投稿机器人自动建循环任务，网站上传不建，导致网站上传的资料不循环。
    """
    # 用 SAVEPOINT（嵌套事务）：循环任务失败只回滚本函数内的变更，
    # 绝不能 db.rollback() 整个事务（那会回滚已设置的 n.status="published"，
    # 导致 Telegram 已发、数据库却说未发布）。
    try:
        with db.begin_nested():
            from datetime import timedelta
            from app.models.content import LoopTask
            from app.models.media import GlobalSetting
            # 检查全局循环开关
            enabled_row = db.query(GlobalSetting).filter(GlobalSetting.key == "loop_enabled").first()
            loop_enabled = (enabled_row.value or "true").lower() in ("true", "1", "yes") if enabled_row else True
            if not loop_enabled:
                return
            # 读全局循环间隔（默认 259200 秒 = 3 天）
            interval_row = db.query(GlobalSetting).filter(GlobalSetting.key == "loop_interval_seconds").first()
            interval = int(interval_row.value or 259200) if interval_row else 259200
            # 同一资料只留一个循环任务记录：已有（可能已停）→ 重新启用并同步全局间隔；没有 → 新建
            # 下架停循环、重新上架自动开启，保持跟全局循环同步
            # 防重复：如果已有多个任务，只保留第一个，其余禁用（之前 bug：create_loop 可建出两个）
            all_tasks = db.query(LoopTask).filter(LoopTask.note_id == n.id).order_by(LoopTask.id).all()
            existing = all_tasks[0] if all_tasks else None
            for _dup in all_tasks[1:]:
                _dup.enabled = False
            if existing:
                existing.enabled = True
                existing.interval_seconds = interval
                existing.next_run_at = datetime.utcnow() + timedelta(seconds=interval)
            else:
                db.add(LoopTask(
                    note_id=n.id,
                    created_by=user.id,
                    interval_seconds=interval,
                    enabled=True,
                    next_run_at=datetime.utcnow() + timedelta(seconds=interval),
                    run_count=0,
                ))
    except Exception:
        # 建循环任务失败不影响本次发布（SAVEPOINT 已回滚本函数变更）
        import logging
        logging.getLogger(__name__).exception("网站上传自动建循环任务失败（不影响本次发布）")


def _send_to_channels(n: Note, user: User, db: Session,
                      channel_ids: list[int] | None = None) -> tuple[list[str], list[str]]:
    """把一组上架内容真实发送到笔记绑定的频道。

    一组 =（文字+混合媒体）打包发送，紧跟一条单独验证视频。
    channel_ids：覆盖发送目标（push_all 全量推送时只发指定频道）。
    返回 (成功频道名, 失败原因)。

    发布前预检：每个频道先验证 Bot 权限，失败的直接记入 failed，不尝试发送。
    """
    from app.api.v1.bots import _dec
    from app.api.v1.media import get_matting_global
    from app.services.publisher import _media_bytes, matt_for_publish, send_listing_set
    from app.api.v1.channel import _verify_bot_channel

    media = db.query(NoteMedia).filter(NoteMedia.note_id == n.id).order_by(NoteMedia.sort_order).all()
    show = [{"url": m.url, "media_type": m.media_type} for m in media if m.kind == "show"]
    verify = [{"url": m.url} for m in media if m.kind == "verify"]

    # 图片顺序打乱：每次发布随机打乱展示图顺序，采集机器人看"一组图"时会觉得不一样
    # 零画质损失，白送的防重
    import random as _random
    _random.shuffle(show)

    # 全局抠图模式：开启后所有发往频道的展示图按所选背景自动抠图（内存处理，不落盘）；
    # 服务器只保留原图，每次循环都拿原图重新处理再发送
    _gm_raw = get_matting_global(user, db)
    _gm = _gm_raw.get("data") if isinstance(_gm_raw, dict) and "data" in _gm_raw else _gm_raw
    gm = _gm if isinstance(_gm, dict) and _gm.get("enabled") else None
    if gm:
        processed = []
        for m in show:
            # 抠图只对图片，视频跳过（之前 bug：视频在 show_media 里也被抠图，PIL 报错"cannot identify image file"）
            mtype = m.get("media_type", "image") if isinstance(m, dict) else "image"
            fname, data = _media_bytes(m["url"])
            if mtype == "video":
                # 视频不抠图，原样发送（后续 vary_video 处理）
                processed.append({"data": data, "name": fname})
                continue
            # 抠图失败必须报错，不得悄悄发原图（用户明确要求）
            data = matt_for_publish(data, None, db, user, "替换背景", None)
            processed.append({"data": data, "name": fname})
        show = processed

    sent, failed = [], []
    cids = channel_ids if channel_ids is not None else (n.channel_ids or [])
    for cid in cids:
        # 只能发布到自己的频道（之前 bug：无所有权过滤，可发布到他人频道用他人 Bot）
        _ch_q = db.query(Channel).filter(Channel.id == cid)
        if user is not None and user.id is not None:
            _ch_q = _ch_q
        ch = _ch_q.first()
        if not ch:
            failed.append(f"频道#{cid}：频道不存在或不属于你")
            continue
        if not ch.is_active:
            continue
        # 发布前预检：验证 Bot 权限
        ok_v, msg_v = _verify_bot_channel(db, ch)
        if not ok_v:
            failed.append(f"{ch.name}：发布前预检失败 - {msg_v}")
            continue
        chat = ch.tg_channel_id or ch.username
        if not chat:
            failed.append(f"{ch.name}：未配置频道地址")
            continue
        if not ch.bot_id:
            failed.append(f"{ch.name}：未绑定推送 Bot")
            continue
        # Bot 也必须属于当前用户
        _bot_q = db.query(BotToken).filter(BotToken.id == ch.bot_id)
        if user is not None and user.id is not None:
            _bot_q = _bot_q
        bot = _bot_q.first()
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

        # 文字处理：首次发原文，循环重发才处理（用户定）
        # 首次：variation=False，发原文
        # 循环：已有成功 TaskLog，variation=True，处理文字（打乱三行 + 中文写法）
        use_variation = bool(gm) and bool(getattr(ch, "variation_enabled", True)) and db.query(TaskLog).filter(
            TaskLog.note_id == n.id, TaskLog.action == "push_send",
            TaskLog.result == "success",
            TaskLog.detail.contains(ch.name)).first() is not None
        try:
            res = send_listing_set(
                _dec(bot.token_secret), chat,
                title=n.title, body=n.body, tags=n.tags,
                show_media=show, verify_media=verify,
                # 全局抠图已处理则不再叠加频道防扫图
                anti_scan_mode="原图" if gm else (ch.anti_scan_mode or "原图"),
                resume=ch_progress, on_step=_mark_step,
                variation=use_variation,
                author_user_id=user.id,  # 个人水印（P1-14）：按作者设置叠加
                note_id=n.id,  # 视频镜像交替用（按发布次数）
                db=db,  # 文字轮流变体查发布次数用
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


def _delete_note_receipts_sync(db, note_id: int) -> tuple[int, list[str]]:
    """同步删除笔记的所有未删回执，Telegram 确认后才算成功。

    返回 (handled_count, errors)：
    - handled_count：已确认删除（或消息已不存在/已超 Bot 可删除期限）的消息数
    - errors：真正的失败描述列表；为空表示全部确认
    回执 deleted 标记随处理结果更新；失败的不标记，可重试。
    """
    from app.models.content import PublishReceipt
    from app.models.account import BotToken
    from app.api.v1.bots import _dec, _bot_api

    receipts = db.query(PublishReceipt).filter(
        PublishReceipt.note_id == note_id,
        PublishReceipt.deleted.is_(False),
    ).all()
    handled, errors = 0, []
    for r in receipts:
        try:
            if r.bot_id:
                bot = db.query(BotToken).filter(BotToken.id == r.bot_id).first()  # 删帖用原发送 Bot，无需 user 隔离（回执已按用户过滤）
                if not bot:
                    raise ValueError(f"Bot#{r.bot_id} 不存在")
                _bot_api(_dec(bot.token_secret), "deleteMessage",
                         {"chat_id": r.chat_id, "message_id": r.message_id})
            elif r.account_id:
                # 协议号通道：用 Telethon 删除
                # 用专用线程 loop（之前 bug：asyncio.run 每次新 loop，共享客户端报 different loop）
                from app.services.tg_client import get_shared_client, run_in_tg_loop
                # 先在主线程查 phone（db Session 非线程安全，不能在协程内用）
                from app.models.account import TgAccount
                _acc = db.query(TgAccount).filter(TgAccount.id == r.account_id).first()
                if not _acc or not _acc.phone:
                    raise ValueError(f"协议号 #{r.account_id} 不存在或无手机号")
                _phone = _acc.phone
                _chat_id = int(r.chat_id)
                _msg_id = r.message_id
                async def _del():
                    client = await get_shared_client(_phone)
                    await client.delete_messages(_chat_id, [_msg_id])
                run_in_tg_loop(_del())
            else:
                raise ValueError(f"回执#{r.id} 无发送通道")
            r.deleted = True
            handled += 1
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            # 消息已不存在，或已超 Bot 可删除期限（48h）：视为已处理，不算失败
            if "message to delete not found" in msg or "message can't be deleted" in msg:
                r.deleted = True
                handled += 1
            else:
                errors.append(f"消息{r.message_id}@{r.chat_id} 删除失败: {msg[:120]}")
    db.flush()
    return handled, errors


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
    n = db.query(Note).first()
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资料不存在")
    if approve:
        _check_verify_video(db, n.id)  # 硬校验：必须且只能 1 个 MP4 验证视频
        action, detail, msg = "review_approve", "审核通过并发布", "审核通过，已发布"
        if not (n.scheduled_at and n.scheduled_at > datetime.utcnow()):
            sent, failed = _send_to_channels(n, user, db)
            n.scheduled_sent = True  # 防 worker 重复发送
            if sent:
                n.status = "published"
                n.published_at = datetime.utcnow()
                _auto_create_loop_task(db, n, user)  # 审核通过发布也自动进循环
            else:
                # 发送全部失败：不标 published，标 publish_failed
                n.status = "publish_failed"
                msg = f"审核通过，但发送失败：{failed[0] if failed else '未知原因'}"
                detail = f"审核通过，发送失败：{'; '.join(failed)[:200]}"
                action = "review_approve_failed"
        else:
            n.status = "published"
            n.published_at = datetime.utcnow()
            _auto_create_loop_task(db, n, user)  # 定时发布也自动进循环
    else:
        n.status = "offline"
        # 审核拒绝要停循环（防止循环把已拒绝笔记重新发布）
        from app.models.content import LoopTask as _LT3
        for _t3 in db.query(_LT3).filter(_LT3.note_id == n.id, _LT3.enabled.is_(True)).all():
            _t3.enabled = False
        _queue_removal(db, n.id)  # 下架自动删帖
        action, detail, msg = "review_reject", "审核拒绝（下架，可恢复）", "已拒绝（移入下架）"
    result = "success" if "failed" not in action else "fail"
    db.add(TaskLog(note_id=n.id, action=action, executor=user.username, result=result, detail=detail))
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
    publish_details = []
    unpublish_details = []
    for n in notes:
        if op == "publish":
            # 验证视频硬校验（和单条发布一致，防止批量绕过）
            # _check_verify_video 抛 HTTPException，批量中要捕获，跳过该条而非崩整个批次
            try:
                _check_verify_video(db, n.id)
            except HTTPException as _ve:
                publish_details.append(f"笔记 {n.id} 验证视频校验失败：{_ve.detail}")
                n.status = "publish_failed"
                continue
            if user is not None and not (n.scheduled_at and n.scheduled_at > datetime.utcnow()):
                sent, failed = _send_to_channels(n, user, db)
                n.scheduled_sent = True  # 防 worker 重复发送
                if sent:
                    n.status = "published"
                    n.published_at = datetime.utcnow()
                    _auto_create_loop_task(db, n, user)  # 批量发布进循环
                else:
                    n.status = "publish_failed"
                    if failed:
                        publish_details.append(f"笔记#{n.id}: {'; '.join(failed)}")
                    elif not (n.channel_ids or []):
                        publish_details.append(f"笔记#{n.id}: 未选择推送频道")
                    else:
                        publish_details.append(f"笔记#{n.id}: 频道未激活或未绑定Bot")
            else:
                n.status = "published"
                n.published_at = datetime.utcnow()
                _auto_create_loop_task(db, n, user)  # 定时批量发布进循环
        elif op == "unpublish":
            # 同步删帖确认后才翻 offline；失败的不翻，记入警告可重试
            _handled, _errors = _delete_note_receipts_sync(db, n.id)
            if _errors:
                unpublish_details.append(f"笔记#{n.id}: {'; '.join(_errors[:2])}")
            else:
                n.status = "offline"
                # 批量下架 → 停止循环（和单条下架同逻辑）
                from app.models.content import LoopTask as _LT2
                for _t2 in db.query(_LT2).filter(_LT2.note_id == n.id, _LT2.enabled.is_(True)).all():
                    _t2.enabled = False
        elif op == "delete":
            # 同步删磁盘文件（与素材删除一致），避免 uploads 残留
            # 先查文件是否被其他笔记共享，共享的不删
            from app.api.v1.media import _fs_path
            for m in db.query(NoteMedia).filter(NoteMedia.note_id == n.id).all():
                try:
                    # 检查其他笔记是否引用同一文件
                    shared = db.query(NoteMedia).filter(
                        NoteMedia.url == m.url,
                        NoteMedia.note_id != n.id).first()
                    if not shared:
                        fp = _fs_path(m.url)
                        if os.path.exists(fp):
                            os.remove(fp)
                except Exception:
                    pass
            db.query(NoteMedia).filter(NoteMedia.note_id == n.id).delete()
            # 批量删除要清理循环任务（防止孤儿任务每轮报错重试）
            from app.models.content import LoopTask as _LT4
            db.query(_LT4).filter(_LT4.note_id == n.id).delete()
            # 清理发布回执 + 入删帖队列（删除 Telegram 消息）
            from app.models.content import PublishReceipt as _PR
            db.query(_PR).filter(_PR.note_id == n.id).delete()
            _queue_removal(db, n.id)
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
    if publish_details:
        extra["publish_warnings"] = publish_details
    if unpublish_details:
        extra["unpublish_warnings"] = unpublish_details
    return {"count": count, **extra}


@router.post("/batch")
def batch_op(body: BatchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(body.ids) > 500:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "批量操作最多 500 条")
    # 普通用户仅允许批量上下架，其他批量操作需要会员
    if body.op not in ("publish", "unpublish") and not (user.is_admin or user.is_member):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该功能仅会员可用，请先开通会员")
    notes = db.query(Note).filter(Note.id.in_(body.ids), Note.created_by == user.id).all()
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




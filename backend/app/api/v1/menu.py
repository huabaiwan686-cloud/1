"""动态菜单：GET /api/menu/all（对齐原站 17 页面路由）。"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, ok
from app.models.user import User

router = APIRouter(tags=["menu"])

# 与原站侧边栏一致的路由树（name/path/component 供 vben 前端消费）
MENU_TREE = [
    {"name": "Dashboard", "path": "/admin/dashboard", "title": "工作台"},
    {"name": "AdminUsers", "path": "/admin/users", "title": "账号管理"},
    {
        "name": "Collector",
        "path": "/collector",
        "title": "采集端",
        "children": [
            {"name": "CollectorUpload", "path": "/collector/upload", "title": "上传资料"},
            {"name": "CollectorContent", "path": "/collector/content", "title": "我的内容"},
            {"name": "CollectorRecords", "path": "/collector/records", "title": "采集记录"},
        ],
    },
    {"name": "AdminNotes", "path": "/admin/notes", "title": "笔记列表"},
    {"name": "AdminLogs", "path": "/admin/logs", "title": "任务记录"},
    {"name": "AdminChannels", "path": "/admin/channels", "title": "频道配置"},
    {"name": "AdminMessagePush", "path": "/admin/message-push", "title": "群聊推送"},
    {"name": "PublishMessagePush", "path": "/publish/message-push", "title": "群聊推送"},
    {"name": "AdminGroupListen", "path": "/admin/group-listen", "title": "关键字推送"},
    {"name": "PublishGroupListen", "path": "/publish/group-listen", "title": "关键字推送"},
    {"name": "AdminCollection", "path": "/admin/collection", "title": "代理采集"},
    {"name": "CollectionReview", "path": "/admin/collection/review", "title": "采集审核"},
    {
        "name": "AccountConfig",
        "path": "/admin/accounts",
        "title": "账号配置",
        "children": [
            {"name": "Protocol", "path": "/admin/accounts/protocol", "title": "TG 账号"},
            {"name": "Bots", "path": "/admin/accounts/bots", "title": "Bot Token"},
            {"name": "XcCmsBinding", "path": "/admin/accounts/xc-cms-binding", "title": "平台绑定"},
        ],
    },
    {"name": "TwoWayBots", "path": "/admin/accounts/two-way-bots", "title": "双向机器人"},
    {"name": "PlatformCooperation", "path": "/admin/accounts/platform-cooperation", "title": "平台合作"},
    {"name": "Friends", "path": "/admin/accounts/friends", "title": "好友关注"},
    {"name": "Vip", "path": "/admin/vip", "title": "VIP会员"},
    {"name": "Announcements", "path": "/admin/announcements", "title": "系统公告"},
]


@router.get("/menu/all")
def menu_all(user: User = Depends(get_current_user)):
    if user.is_admin:
        # 去掉 /publish/ 重复项（与 /admin/ 同名）
        return ok([m for m in MENU_TREE if not m["path"].startswith("/publish/")])
    if user.is_member:
        # 会员：除账号管理外的全部功能
        return ok([m for m in MENU_TREE if m["path"] != "/admin/users"])
    # 普通用户：仅上下架（笔记列表的发布/下架）
    return ok([
        {"name": "AdminNotes", "path": "/admin/notes", "title": "上下架"},
    ])

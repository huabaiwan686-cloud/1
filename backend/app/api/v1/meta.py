"""标签 / 城市接口。"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, ok
from app.core.database import get_db
from app.models.content import City, Tag
from app.models.user import User

tag_router = APIRouter(prefix="/tag", tags=["tag"])
city_router = APIRouter(prefix="/city", tags=["city"])


@tag_router.get("/list")
def list_tags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tags = db.query(Tag).filter(Tag.status == "approved").order_by(Tag.id).all()
    return ok([{"id": t.id, "name": t.name} for t in tags])


@tag_router.post("/create")
def create_tag(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(Tag).filter(Tag.name == name).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "标签已存在")
    # 新标签进入审核（对齐原站）
    t = Tag(name=name, status="pending")
    db.add(t)
    db.commit()
    return ok({"id": t.id, "name": t.name}, msg="标签已提交审核")


@city_router.get("/tree")
def city_tree(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cities = db.query(City).order_by(City.level, City.id).all()
    by_parent: dict[int | None, list] = {}
    for c in cities:
        by_parent.setdefault(c.parent_id, []).append({"id": c.id, "name": c.name, "children": []})
    # 简单两级组装
    id_map = {c.id: {"id": c.id, "name": c.name, "children": []} for c in cities}
    roots = []
    for c in cities:
        node = id_map[c.id]
        if c.parent_id and c.parent_id in id_map:
            id_map[c.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return ok(roots)

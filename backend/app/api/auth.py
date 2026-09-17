"""认证路由：登录 / 当前用户。当前仅超管 admin 一个角色。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_token, get_current_user, verify_password
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginReq(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return {"token": create_token(user), "user": user.to_dict()}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user.to_dict()

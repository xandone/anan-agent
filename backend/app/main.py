from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, categories, chat, collect, config, conversations, videos
from app.core.database import init_db
from app.core.security import get_current_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="anan-agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 登录/登出不需要鉴权
app.include_router(auth.router)

# 其余所有接口需要登录（当前仅超管 admin 一个角色，登录即全权限）
_auth = [Depends(get_current_user)]
app.include_router(collect.router, dependencies=_auth)
app.include_router(videos.router, dependencies=_auth)
app.include_router(categories.router, dependencies=_auth)
app.include_router(chat.router, dependencies=_auth)
app.include_router(conversations.router, dependencies=_auth)
app.include_router(config.router, dependencies=_auth)


@app.get("/api/health")
def health():
    return {"status": "ok"}

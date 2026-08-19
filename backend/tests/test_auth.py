"""POST /api/auth/register + /api/auth/login 单测。

覆盖：注册成功 201、登录成功 200、重复邮箱 409、错误密码 401、
password_hash 不回传且为 bcrypt、鉴权依赖 Bearer token。
"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.db import Base, get_db
from app.main import app
from app.models import User
from app.security import decode_token, get_current_user, verify_password

# 独立的内存 SQLite（与现有句子测试同模式，避免触碰真实种子数据）
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _register(client, email="a@b.com", password="123456", nickname="老泰州"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "nickname": nickname},
    )


def test_register_success_201(client):
    resp = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"token", "user"}
    assert body["user"] == {"id": 1, "email": "a@b.com", "nickname": "老泰州"}
    # token 能解析回该用户
    assert decode_token(body["token"]) == 1


def test_register_stores_bcrypt_not_plaintext(client):
    _register(client)
    with TestingSessionLocal() as db:
        u = db.execute(select(User).where(User.email == "a@b.com")).scalar_one()
        # 库里是 bcrypt 哈希，不是明文
        assert u.password_hash != "123456"
        assert verify_password("123456", u.password_hash) is True
        assert u.total_score == 0


def test_register_response_has_no_password_hash(client):
    resp = _register(client)
    body = resp.json()
    assert "password_hash" not in body["user"]
    assert "password" not in body


def test_duplicate_email_returns_409(client):
    assert _register(client).status_code == 201
    resp = _register(client, email="a@b.com", nickname="another")
    assert resp.status_code == 409


def test_login_success_200(client):
    _register(client)
    resp = client.post(
        "/api/auth/login", json={"email": "a@b.com", "password": "123456"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"token", "user"}
    assert body["user"]["email"] == "a@b.com"
    assert decode_token(body["token"]) == 1


def test_login_wrong_password_401(client):
    _register(client)
    resp = client.post(
        "/api/auth/login", json={"email": "a@b.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_login_unknown_email_401(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "nobody@b.com", "password": "123456"},
    )
    assert resp.status_code == 401


def test_register_weak_password_rejected(client):
    resp = _register(client, password="123")
    assert resp.status_code == 422


def test_register_empty_nickname_rejected(client):
    resp = _register(client, nickname="")
    assert resp.status_code == 422


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_get_current_user_dependency():
    """验证鉴权依赖：合法 token 拿到用户，缺失/伪造 token 抛 401。"""
    # 用主 client 的库结构（两条查询 Level 同库）构造一名用户
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.security import hash_password, create_token

    with TestingSessionLocal() as db:
        db.add(
            User(
                email="dep@b.com",
                password_hash=hash_password("123456"),
                nickname="依赖",
                total_score=0,
            )
        )
        db.commit()
        user_id = db.execute(
            select(User).where(User.email == "dep@b.com")
        ).scalar_one().id

    probe = FastAPI()
    probe.dependency_overrides[get_db] = _override_get_db

    @probe.get("/me")
    def me(user: User = Depends(get_current_user)):
        return {"id": user.id, "email": user.email}

    tc = TestClient(probe)
    valid_token = create_token(user_id)
    # 有效 Bearer token → 200，拿到当前用户
    ok = tc.get("/me", headers={"Authorization": f"Bearer {valid_token}"})
    assert ok.status_code == 200
    assert ok.json() == {"id": user_id, "email": "dep@b.com"}
    # 无 token → 401
    assert tc.get("/me").status_code == 401
    # 伪造/非法 token → 401
    assert (
        tc.get("/me", headers={"Authorization": "Bearer not-a-real-token"}).status_code
        == 401
    )
    probe.dependency_overrides.clear()

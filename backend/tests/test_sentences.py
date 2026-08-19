"""GET /api/sentences 接口单测（不启动 dev server）。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import MAX_SENTENCES, app
from app.models import Sentence

# 独立的内存 SQLite：用 StaticPool 保证所有连接共享同一个库，
# 避免触碰真实种子数据（sqlite:///:memory: 默认每个连接独立库）
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed_sentences(count: int) -> None:
    with TestingSessionLocal() as db:
        for i in range(count):
            db.add(
                Sentence(
                    text=f"普通话句{i}",
                    dialect_text=f"方言句{i}",
                    category="test",
                    difficulty=1,
                )
            )
        db.commit()


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed_sentences(20)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # 不用 `with TestClient(app)`，避免触发 lifespan（后台预热 ASR 模型，本测试用不到）
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_default_n_is_5(client):
    resp = client.get("/api/sentences")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sentences"]) == 5
    for s in body["sentences"]:
        assert set(s) == {"id", "text", "dialect_text"}


def test_returns_n_sentences(client):
    resp = client.get("/api/sentences", params={"n": 3})
    assert resp.status_code == 200
    assert len(resp.json()["sentences"]) == 3


def test_n_is_capped_at_max(client):
    resp = client.get("/api/sentences", params={"n": 9999})
    assert resp.status_code == 200
    # 库中仅 20 条，返回条数 = min(9999, MAX_SENTENCES, 20) = 20
    assert len(resp.json()["sentences"]) == 20


def test_random_distinct_ids(client):
    resp = client.get("/api/sentences", params={"n": 5})
    ids = [s["id"] for s in resp.json()["sentences"]]
    assert len(ids) == len(set(ids))  # 不重复


def test_invalid_n_rejected(client):
    resp = client.get("/api/sentences", params={"n": 0})
    assert resp.status_code == 422
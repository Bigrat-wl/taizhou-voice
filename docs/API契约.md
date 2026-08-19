# 泰州方言通 API 契约（v2）

> 日期：2026-08-19 · 状态：已定稿（v2），待实现
> 定位：让前后端先对齐请求参数、响应结构、错误码。**先对齐契约，再写实现。**
> 已实现端点（`/health`、`/api/asr`）以代码为准；未实现端点以本文档为蓝本。

---

## 0. 通用约定

### Base URL

- 开发：`http://localhost:8000`（前端经 proxy 走 `/api`）
- 生产：`http://<游戏本IP>:8000`（演示阶段 IP 直连，靠后端 CORS）

### 响应格式

**成功**：直接返回资源对象或数组，不做 `{ data: ... }` 包裹。

```json
// 200 GET /api/sentences?n=3
{
  "sentences": [
    { "id": 1, "text": "今天天气真好", "dialect_text": "今朝天气老好" }
  ]
}
```

**分页/榜单**：需要元数据时单独加字段，普通列表直接给数组。

**错误**：HTTP 状态码语义化 + 统一错误体：

```json
{ "detail": "不支持的音频格式: .xyz" }
```

> FastAPI 默认错误体（`detail` 字段），前端拦截非 2xx 读 `detail` 提示即可。

### 认证

- 演示期最简**邮箱 + 密码**用户系统：注册/登录后下发 token，受保护端点带 `Authorization: Bearer <token>`。
- 未登录访问受保护端点 → `401`；token 实现（JWT 或 DB session）由后端自选，前端不关心。

### 时间格式

- 一律 ISO 8601 **中国时区**：`"2026-08-19T20:00:00.000+08:00"`；相对时间由前端格式化。

### 评分与颜色（前端展示）

- 后端只给 `score`（0~100 整数）。颜色/文案由前端映射：
  - 🟢 优秀：`score >= 90`
  - 🟡 中等：`60 <= score < 90`
  - 🔴 不及格：`score < 60`
- **及格线 = 60**：`score >= 60` 计入「正确数」。

---

## 1. 端点清单

### 1.1 健康检查 Health

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/health` | 否 | 服务状态 + 模型是否加载 |

**响应：**

```json
{ "status": "ok", "model_loaded": true }
```

### 1.2 语音识别 ASR（已实现）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/asr` | 否 | 音频 → 普通话文本（转写页复用） |

**请求**：`multipart/form-data`，字段名 `audio`（支持 `.wav/.mp3/.flac/.ogg/.m4a/.wma/.aac/.webm`）。

**响应 200：**

```json
{ "text": "今天天气真好", "language": "Chinese" }
```

### 1.3 认证 Auth（待实现）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/auth/register` | 否 | 注册：`{ email, password, nickname }` → 201 |
| POST | `/api/auth/login` | 否 | 登录：`{ email, password }` → 200 |

**注册请求体：**

```json
{ "email": "a@b.com", "password": "123456", "nickname": "老泰州" }
```

- `email` 唯一（撞邮箱 → `409`）；`nickname` ≤64 字；密码至少 6 位（演示期宽松校验）。

**登录/注册成功响应：**

```json
{ "token": "<jwt-or-session>", "user": { "id": 1, "email": "a@b.com", "nickname": "老泰州" } }
```

### 1.4 句子 Sentences（已实现 · 任务 #3）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/sentences` | 否 | 随机取 N 句（挑战赛刷题），`?n=` 默认 5，最大 50 |

**响应 200：**

```json
{
  "sentences": [
    { "id": 1, "text": "今天天气真好", "dialect_text": "今朝天气老好" }
  ]
}
```

- 已按此格式实现（含 5 个单测），字段 `{ id, text, dialect_text }`；`n` 超出范围按上限截断。

### 1.5 评分 Score（待实现 · 任务 #5）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/score` | **是** | 上传录音 → 识别 → 与参考文本比对打分 → 存录音+分数 |

**请求**：`multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `audio` | file | 是 | 用户录音 |
| `sentence_id` | int | 是 | 对应句子 id |

**响应 200：**

```json
{ "score": 87, "transcript": "今天天气真好", "reference": "今天天气真好" }
```

- `score`：识别文本 ↔ 参考文本相似度（0~100 整数，内部浮点取整）。
- 录音落盘 `backend/data/audio/{sentence_id}_{user_id}_{ts}.wav`，路径与分数存 `recordings`；`score >= 60` 计入正确数。
- `user` 由 token 解析，不随请求传。

**错误**：`400` 缺字段/句子不存在；`401` 未登录；`415` 音频格式；`422` 未识别到语音。

### 1.6 排行榜 Leaderboard（待实现 · 任务 #6）

**两种榜，分开端点：**

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/leaderboard/correct` | 否 | **正确数榜**（累计答对句子量排名） |
| GET | `/api/sentences/{id}/recordings` | 否 | **点赞数榜**（某句子下所有录音，按点赞数降序） |

**正确数榜响应：**

```json
[
  { "rank": 1, "nickname": "老泰州", "correct_count": 12, "total_score": 950, "best_score": 98 }
]
```

- 按正确数降序（`score >= 60` 的录音数），`?limit=` 默认 20。
- `correct_count` 实时 `COUNT`；`total_score`/`best_score` 作辅助展示。

**点赞数榜响应（某句子）：**

```json
{
  "sentence": { "id": 1, "text": "今天天气真好", "dialect_text": "今朝天气老好" },
  "items": [
    { "recording_id": 10, "nickname": "小明", "audio_url": "/data/audio/xxx.wav", "like_count": 8, "liked_by_me": false }
  ]
}
```

- 按 `like_count` 降序；`liked_by_me` 带 token 时按当前用户算，不带 token 恒为 `false`。
- `audio_url` 供前端播放（「别人录、别人听」的词典式交互）。

### 1.7 点赞 Like（待实现）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/recordings/{id}/like` | **是** | 点赞（幂等：已点返回 200 不报错） |
| DELETE | `/api/recordings/{id}/like` | **是** | 取消点赞（幂等） |

**响应 200：**

```json
{ "like_count": 9, "liked_by_me": true }
```

### 1.8 语音合成 TTS（待实现 · 任务 #11）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/tts` | 否 | 文本 → 方言音频（CosyVoice2） |

**请求**：JSON `{ "text": "今朝天气老好" }`（`text` 必填，≤200 字）。

**响应 200**：`{ "audio_url": "/data/audio/tts_xxx.wav" }`（落盘返回 URL，方案见 §3）。

### 1.9 音频互转 Convert（待实现 · 任务 #12）

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/convert` | 否 | 方言音频 ↔ 普通话音频 |

**请求**：`multipart/form-data`：`audio`（file）+ `direction`（`dialect2mandarin` / `mandarin2dialect`）。

**响应 200**：`{ "audio_url": "/data/audio/conv_xxx.wav" }`。

---

## 2. 错误码速查

| 状态码 | 场景 | detail 示例 |
|--------|------|-------------|
| 400 | 参数缺失/非法 | `sentence_id 必填` |
| 401 | 未登录/token 失效 | `未登录或登录已过期` |
| 403 | 无权限 | — |
| 404 | 资源不存在 | `句子不存在` / `录音不存在` |
| 409 | 邮箱已被注册 | `该邮箱已被注册` |
| 415 | 不支持的音频格式 | `不支持的音频格式: .xyz` |
| 422 | 未识别到语音 | `未识别到有效语音内容` |
| 500 | 识别/合成失败 | `识别失败: ...` |
| 503 | 模型未加载（GPU 缺失等） | `TTS 模型未加载` |

> 幂等操作（点赞/取消点赞）成功与「本就处于目标状态」都返回 200，不返回 409。

---

## 3. 待评审/待定决策

1. **TTS/互转返回方式**：默认落盘返回 `audio_url`；是否改为直接音频流（省一次落盘、免清理）待定。
2. **`/api/sentences` 随机性**：是否排除当前用户已答过的句子（需用户维度，演示期可不做）。
3. **点赞数榜分页**：某句子录音可能很多，是否要 `?limit=` 分页（演示期先全量）。
4. **单词题库后置**：单词的录音/点赞/排行榜接口与句子同构，届时复用本契约（`/api/words/{id}/recordings` 等）。

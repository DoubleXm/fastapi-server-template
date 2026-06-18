# 项目 Agent 规范

本文件是当前仓库唯一的项目级开发规范和编码规范入口。任何 agent 或开发者在修改本项目时，应先阅读本文件；需要了解项目启动、目录说明、检查命令时，再阅读 `README.md`。

## 阅读入口

- `AGENTS.md`：项目分层、编码规范、注释规范、日志规范、枚举规范和修改顺序。
- `README.md`：项目目录、启动方式、Docker、文档地址、校验命令、环境文件和日志概要。

## 项目结构

当前项目按 API 层、核心设施、业务模块和共享工具组织：

```text
app/
├── main.py               # FastAPI app 创建、middleware、router、lifespan 注册
├── api/
│   ├── deps.py           # 全局 FastAPI 依赖：Session、鉴权、分页
│   ├── router.py         # API router 汇总入口
│   ├── schemas.py        # 全局 ApiSchema / ApiResponse
│   └── v1/
│       ├── auth/         # 登录、注册、第三方登录等认证入口
│       └── users/        # users CRUD 和当前用户信息
├── core/
│   ├── config.py         # env 配置读取
│   ├── database.py       # SQLModel engine/session/table 创建
│   ├── exception_handlers.py
│   └── logger/           # Loguru、SQLAlchemy、Uvicorn 等日志配置
├── middlewares/          # 自定义的中间件
└── shared/               # 轻框架依赖的工具、常量、安全方法
alembic/                  # Alembic 数据库迁移脚本
```

新增 API 模块时，优先复用现有按业务域组织的结构：

```text
app/api/v1/<module>/
├── __init__.py
├── models.py             # SQLModel table
├── schemas.py            # API input/output schema
├── repository.py         # 数据访问
├── service.py            # 业务逻辑
├── router.py             # FastAPI endpoints
└── deps.py               # 可选：只有存在模块级依赖时才创建
```

`deps.py` 不是每个模块必需。只有当模块有真实可复用依赖时才创建，例如模块级权限、复杂 path/query 组合、租户上下文等。不要为了重命名单个参数或包一层简单函数创建 `deps.py`。

## 模块变更规范

新增、修改和删除模块都应保持分层边界清晰，优先让每次变更只覆盖一个业务意图。除非当前需求明确要求重构，否则不要把模块迁移、命名调整和业务行为变化混在同一次改动里。

新增 API 模块时：

1. 先阅读现有 `users` 模块和相关测试，确认当前项目模式。
2. 按 `models.py`、`schemas.py`、`repository.py`、`service.py`、`router.py` 的顺序实现；只有存在真实可复用依赖时才新增模块级 `deps.py`。
3. 在 `app/api/router.py` 注册 router。
4. 如新增 SQLModel table，在 `app/core/database.py:import_model_modules` 导入模型。
5. 测试需要 metadata 时，在 `tests/conftest.py` 导入模型。
6. 新增或更新 Alembic migration，并人工 review 字段类型、索引、comment、默认值和数据迁移逻辑。
7. 补充聚焦测试，覆盖 service 核心规则和 router/API 行为。

修改已有模块时：

1. 行为变化先补充或更新测试，确保测试描述业务行为而不是实现细节。
2. 保持 router、service、repository、schema、model 的职责边界，不为省事跨层调用。
3. 修改数据库字段时同步更新模型、migration 和字段 comment 测试。
4. 修改 API 入参/出参时同步检查 lowerCamelCase、统一 response、分页和鉴权测试。
5. 修改日志、鉴权、异常处理等共享行为时，补充对应 middleware/formatter/dependency 测试。

删除模块时：

1. 先确认没有 router 注册、模型导入、测试 fixture、migration、文档或第三方服务仍引用该模块。
2. 移除 `app/api/router.py` 中的 router 注册。
3. 移除 `app/core/database.py:import_model_modules` 和 `tests/conftest.py` 中的模型导入。
4. 删除或更新相关测试，保留能证明新行为的测试。
5. 如删除数据库表或字段，新增 Alembic migration，不要只删除 SQLModel 代码。
6. 清理无用配置、常量、第三方 client/service 和依赖项，避免留下死代码。

## 修改顺序

修改业务模块时，优先遵循“模块变更规范”中的新增、修改、删除流程。通用修改按以下稳定顺序推进，减少跨层跳改导致的不可预测问题：

1. 阅读现有模块和测试，确认当前项目模式。
2. 行为变化先补充或更新聚焦测试。
3. 修改 `models.py`，定义 SQLModel table 和数据库字段 comment。
4. 修改 `schemas.py`，定义 API 输入/输出模型和必要校验。
5. 修改 `repository.py`，封装数据库访问。
6. 修改 `service.py`，封装业务逻辑和 HTTP 异常。
7. 如确有必要，新增或修改模块级 `deps.py`。
8. 修改 `router.py`，声明 endpoint、依赖和统一 response。
9. 在 `app/api/router.py` 注册 router。
10. 在 `app/core/database.py:import_model_modules` 导入表模型。
11. 测试需要 metadata 时，在 `tests/conftest.py` 导入表模型。
12. 生成或更新 Alembic migration，并人工 review 字段类型、索引、comment、默认值和数据迁移逻辑。
13. 按文档职责更新说明：
    - 只有权限模型、token 策略、日志架构、异常策略、迁移策略、分层规则、第三方集成边界等核心约束变化，或当前 `AGENTS.md` 已不足以约束后续迭代时，才更新 `AGENTS.md`。
    - 启动方式、目录结构、模板功能、接口说明、命令、环境变量和使用说明变化时，更新 `README.md`。
    - 普通业务模块新增、删除、重命名，只要符合既有约束，不应为了记录变化而更新 `AGENTS.md`。
14. 运行验证：
    - `uv run ruff check app tests`
    - `uv run pytest -q`

除非重构是实现当前需求所必需，否则把重构和功能改动分开。

## 编码规范总则

- 保持代码接近现有风格，优先复用当前 helper、schema、依赖和分层模式。
- 使用 Python 3.11+ 类型写法：`str | None`、`list[Model]`。
- 不使用 `Optional`、`List` 等旧式 typing，除非兼容性要求明确存在。
- 不在 router 中写数据库查询或复杂业务逻辑。
- 不在 repository 中抛业务 HTTP 异常；repository 只处理数据访问。
- 不在 service 中拼 API response；service 返回模型或业务结果。
- 不在 shared 中放 FastAPI `Depends`、`Query`、router dependency 或 API response schema。
- lifespan 逻辑默认保留在 `app/main.py`。只有启动和关闭流程复杂度较高，例如挂载多个定时任务、外部连接、后台 worker 或资源编排逻辑时，才建议抽离到单独文件。
- 修改行为时优先增加测试；测试命名描述行为，不写泛泛的 `test_works`。

## SQLModel 模型规范

数据库表使用 SQLModel：

```python
class Item(SQLModel, table=True):
    __tablename__ = "items"
```

字段规则：

- 每个数据库字段都要有中文数据库 `comment`。
- 常规字段只写数据库 comment，不必写 OpenAPI `description`。
- 枚举、开关、状态、领域含义复杂字段需要补充 `description`。
- 显式使用 SQLAlchemy `Column` 时，comment 写到 `Column`。

常规字段示例：

```python
title: str = Field(
    max_length=100,
    nullable=False,
    sa_column_kwargs={"comment": "标题"},
)
```

开关字段示例：

```python
is_completed: bool = Field(
    default=False,
    nullable=False,
    description="是否完成",
    sa_column_kwargs={"comment": "是否完成"},
)
```

时间字段示例：

```python
created_at: datetime = Field(
    default_factory=utc_now,
    sa_column=Column(DateTime(timezone=True), nullable=False, comment="创建时间"),
)
```

## 数据库迁移规范

数据库 schema 变更统一通过 Alembic 管理，不依赖应用启动时隐式改表。

- 新增或修改 SQLModel table 后，必须同步新增或更新 `alembic/versions/` 下的迁移文件。
- 生成迁移使用 `uv run alembic revision --autogenerate -m "message"`。
- 执行迁移使用 `uv run alembic upgrade head`。
- 回滚验证使用 `uv run alembic downgrade -1`，必要时再 `upgrade head` 回到最新版本。
- 自动生成的迁移必须人工 review，重点检查字段类型、索引、unique、nullable、default、comment 和数据迁移逻辑。
- `CREATE_DB_TABLES` 只允许用于本地或测试快速初始化；生产环境即使设置为 `true` 也不会自动建表。
- 新模块的表模型要加入 `app/core/database.py:import_model_modules`，确保 Alembic metadata 能发现。
- 应用启动时是否执行 `SQLModel.metadata.create_all` 由 `CREATE_DB_TABLES` 和 `APP_ENV` 共同控制；不要在业务代码里绕过该判断直接调用 `create_all` 作为正式建表或改表方案。

## Schema 规范

- API schema 继承 `app.api.schemas.ApiSchema`。
- 外部 API 输入/输出使用 lowerCamelCase。
- Python 内部字段保持 snake_case。
- Create / Update / Public schema 分开定义。
- 当 Create / Update / Public 之间存在稳定共享字段时，可以抽出 `<Module>Base` 复用字段定义；base 通常继承 `ApiSchema`，具体 schema 再继承 base。不要为了偶然重复的少量字段过度抽象。
- Update schema 字段一般为可选，并在 service 中使用 `model_dump(exclude_unset=True)`。
- `description` 只给枚举、开关、状态和难理解字段使用。

示例：

```python
class ItemCreate(ApiSchema):
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ItemUpdate(ApiSchema):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    is_completed: bool | None = None
```

## Repository 规范

repository 只负责数据库访问，不写业务异常，不组装 response。

推荐模式：

```python
def get_item_by_id(session: Session, item_id: int) -> Item | None:
    return session.get(Item, item_id)


def list_items(session: Session, *, skip: int, limit: int) -> tuple[list[Item], int]:
    total = session.exec(select(func.count()).select_from(Item)).one()
    items = session.exec(
        select(Item).order_by(Item.id.desc()).offset(skip).limit(limit)
    ).all()
    return list(items), total
```

写入操作负责 `add/commit/refresh`，保持与现有 users 模块一致。

## Service 规范

service 负责业务规则、校验和 HTTP 异常，不负责 FastAPI response envelope。

推荐模式：

```python
def get_item_or_404(session: Session, item_id: int) -> Item:
    item = repository.get_item_by_id(session, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item
```

更新操作使用 `exclude_unset=True`，避免把未传字段写成 `None`：

```python
updates = payload.model_dump(exclude_unset=True)
if not updates:
    return item
return repository.update_item(session, item=item, updates=updates)
```

## Router 规范

router 只处理 HTTP 层：

- 声明路径、依赖、状态码和 response model。
- 调用 service。
- 使用 `ApiResponse.success(...)` 统一返回。
- 不在 router 中写数据库查询。
- 不写无用的 `request: Request` 参数。
- 不添加无意义的 `summary`。

列表接口使用 `PaginationDep`，返回 `data + total`：

```python
@router.get("", response_model=ApiResponse[list[ItemPublic]])
def read_items(session: SessionDep, pagination: PaginationDep) -> dict:
    items, total = service.list_items(
        session,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse.success(data=[...], total=total)
```

需要登录后访问的接口使用：

```python
dependencies=[Depends(get_current_user)]
```

如果 endpoint 需要当前用户对象，则使用 `CurrentUser`。

## API Response 规范

- 所有 API response 使用 `app.api.schemas.ApiResponse`。
- 所有 API schema 使用 `app.api.schemas.ApiSchema`。
- 成功响应包含 `code`、`data`。
- 列表成功响应额外包含 `total`。
- 失败响应包含 `code`、`message`，必要时用 `data` 承载具体错误。
- `data` 直接承载业务对象，不再包无意义的业务 key。

列表响应：

```json
{
  "code": 200,
  "data": [],
  "total": 0
}
```

## 鉴权和依赖

- 全局 FastAPI 依赖放在 `app/api/deps.py`。
- 当前模板采用“登录后可操作”的权限模型，不做 owner-only 限制。
- `auth/` 负责登录、注册、refresh token、logout、第三方登录、扫码登录等认证入口。
- `users/` 负责用户资源 CRUD、用户资料和 `/users/me`。
- `auth` 可以调用 `users` 的 repository 或 service 完成查用户、建用户；`users` 不反向依赖 `auth`。
- 新增认证能力优先放在 `auth` 模块，不要塞回 `users` 模块。
- 请求 token 从 `Authorization: Bearer <token>` 读取。
- 登录和注册接口通过 response body 的 `data.token` 返回 token，不通过 response header 返回 token。
- 业务模块只有在确实存在模块级依赖时才创建 `deps.py`。

## 第三方集成规范

涉及第三方组件、SDK 或外部 API 集成时，按依赖方向拆分 `infra` 和应用侧 `services`，不要把第三方请求散落在 router、业务 service 或 shared 工具里。

推荐结构可以从以下形式开始，但文件名和拆分粒度不是强约束，应随 provider 和业务复杂度调整：

```text
infra/
├── __init__.py
└── <provider>/
    ├── __init__.py
    ├── api.py               # 可选：统一管理第三方真实接口地址、path 和 endpoint 常量
    ├── client.py            # 可选：第三方 client，封装 httpx/SDK 调用、鉴权头和底层请求
    └── schemas.py           # 可选：第三方 request/response 数据结构

app/services/
├── __init__.py
└── <provider>_service.py    # 应用侧 service，编排 client 能力并转换为业务语义
```

规则：

- `infra/` 只处理外部系统适配：client 初始化、请求发送、响应解析、第三方错误转换、重试/超时等基础能力。
- 第三方真实地址必须集中管理，不要在 router、service、repository 中散落 URL 字符串；如果是 HTTP API 集成，优先放在对应 provider 的 `infra/<provider>/api.py`。
- `api.py`、`client.py`、`schemas.py` 是推荐起点，不是所有第三方集成都必须创建。对于官方 SDK 型集成，如果 SDK 已经封装了具体接口，可以只保留 `client.py` 和按功能拆分的 SDK 适配文件。
- 第三方 base url、token、timeout 等环境相关配置放在 `app/core/config.py` 的 `Settings` 中，由 client 注入或读取，避免硬编码。
- 如果第三方 client 提供的能力会被业务使用，应在 `app/services/` 创建对应应用 service，通过该 service 暴露业务语义；业务模块调用应用 service，不直接调用 `infra` client。
- `app/services/` 不拼 API response envelope，不依赖 router；它可以编排一个或多个 `infra` client，并把第三方数据转换成当前项目内部模型、schema 或普通业务结果。service 的结构应尽量和 `infra` 中的业务能力对应，避免从项目结构看不出 service 归属。
- 简单集成可以使用单文件，例如 `infra/lark/client.py` 和 `app/services/lark_service.py`；复杂集成可以按业务能力继续拆包，例如 `infra/lark/tasks.py`、`infra/lark/emails.py`，并在 `app/services/lark/` 下保持对应服务边界。具体拆分以当前业务复杂度为准，但仍要保留清晰的外部接口或 SDK 能力边界。
- 如果第三方功能和某个业务模块强绑定，业务模块 service 负责业务规则，`app/services/<provider>_service.py` 负责跨外部系统编排，避免把外部请求写进 repository。
- 测试时优先 mock `infra` client 的边界或用 fake client 注入，避免单元测试真实访问第三方 API。

## 枚举和状态规则

如果系统中出现枚举或状态类概念，优先在 `app/shared/enums.py` 中声明；普通常量优先放在 `app/shared/constants.py`。

规则：

- 使用 Python enum 提升代码可读性。
- 数据库存数字。
- 提供枚举常量和数据库数字之间的映射。
- API 输入/输出使用常量或枚举名，不直接暴露数据库数字。
- 入库前把 API 常量转换为数据库数字。
- 出库后把数据库数字转换为 API 常量。
- 枚举/status 的含义要有中文注释或 `description`。
- 每次新增或修改 `enums.py`、`constants.py` 时，都要自检当前文件是否已经混入过多业务域。复杂度上升时，按业务拆分为 `app/shared/enums/<module.py>` 或 `app/shared/constants/<module>.py`，避免共享文件变成无边界的杂物间。

不要在 router、service、repository 中散落字符串字面量或魔法数字。

## 注释规范

中文注释和 docstring 只在有价值时使用：

- 通用/public 方法或类定义了项目模式时，可以加中文注释。
- 复杂逻辑、边界条件、不明显的取舍应加中文注释。
- 不要给显而易见的代码逐行加注释。
- 程序员通识词汇自然保留英文，例如 `request`、`response`、`handler`、`formatter`、`token`、`SQL`、`body`、`logger`。

推荐：

```python
"""校验 token 并返回当前登录用户。"""
```

避免：

```python
# Assign username to variable
username = payload.username
```

## 日志规范

日志应简洁、可检索、不会泄露敏感信息：

- 程序员通识词汇可以保留英文，例如 `Request body`、`Response body`、`Duration`、`token`、`handler`。
- 非计算机常用词或复杂业务场景可以使用中文。
- 不要无脑全中文，也不要无脑全英文。

## 测试规范

新增行为应补测试：

- service 测试覆盖核心 CRUD、异常和边界。
- router/API 测试覆盖鉴权、统一 response、分页、小驼峰字段。
- 数据库字段 comment 变化要有 metadata 测试。
- 修改日志行为时补 formatter/middleware 测试。

测试使用当前项目的 `db_session` fixture 和 FastAPI `TestClient` 模式。

## Shared vs API vs Core

按依赖方向放置代码：

- `app/api`：FastAPI 相关契约、router、dependencies、API schemas。
- `app/services`：应用侧服务编排，尤其是第三方 client 能力到业务语义的转换。
- `app/core`：应用配置、数据库、日志、异常处理。
- `app/shared`：轻框架依赖的工具、常量、安全辅助方法。
- `infra`：第三方系统适配层，封装 SDK、HTTP client、外部 API 地址和底层请求细节。

避免把 FastAPI `Depends`、`Query`、route dependency 或 API response schema 放进 `shared`。

## Reference

以下文档只在涉及版本差异、不确定行为或需要确认官方用法时按需查阅，不需要每次修改都打开。

- FastAPI 文档：`https://fastapi.tiangolo.com/`
- SQLModel 文档：`https://sqlmodel.tiangolo.com/`
- Pydantic 文档：`https://docs.pydantic.dev/`
- Ruff 文档：`https://docs.astral.sh/ruff/`
- uv 文档：`https://docs.astral.sh/uv/`
- Uvicorn 文档：`https://www.uvicorn.org/`

# FastAPI Template

一个基于 FastAPI、SQLModel、Pydantic、MySQL、JWT、Ruff 和 uv 的后端模板。项目包含用户认证、统一响应、全局异常处理、请求日志、Docker 启动和本地开发规范。

## 目录

```text
.
├── app/                         # 应用源码
│   ├── api/                     # API 层：路由聚合、通用依赖、通用 schemas
│   │   ├── deps.py              # 数据库 Session、登录鉴权、分页 query 依赖
│   │   ├── router.py            # API router 汇总入口
│   │   ├── schemas.py           # ApiSchema / ApiResponse 通用响应结构
│   │   └── v1/                  # v1 接口模块
│   │       ├── auth/            # 登录、注册等认证入口
│   │       └── users/           # users CRUD 和当前用户信息
│   ├── core/                    # 核心配置、数据库、日志、异常处理
│   ├── middlewares/             # 请求日志等中间件
│   ├── shared/                  # 跨层复用工具、常量、枚举、安全方法
│   └── main.py                  # FastAPI app 创建和中间件/router 注册
├── tests/                       # 单元测试和接口行为测试
├── alembic/                     # Alembic 数据库迁移脚本
├── static/                      # 静态资源目录
├── logs/                        # 本地日志输出目录
├── .env.example                 # 环境变量示例
├── .env.test                    # 测试环境配置
├── .editorconfig                # 编辑器基础格式规范
├── .pre-commit-config.yaml      # pre-commit 检查配置
├── .vscode/settings.json        # VS Code / Cursor 保存格式化配置
├── docker-compose.yaml          # 本地 Docker Compose 编排
├── Dockerfile                   # 应用镜像构建文件
├── alembic.ini                  # Alembic 配置
├── pyproject.toml               # 项目依赖和工具配置
└── uv.lock                      # uv 锁文件
```

## 本地启动

安装依赖：

```bash
uv sync --dev
```

启动 MySQL：

```bash
docker compose up mysql -d --build
```

启动应用：

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Docker 启动

```bash
docker compose up --build
```

应用容器启动时会先执行 `uv run alembic upgrade head`，再启动 Uvicorn。应用默认暴露 `8000`，MySQL 默认暴露 `3306`。

## 数据库迁移

数据库 schema 变更统一通过 Alembic 管理：

```bash
# 根据当前 SQLModel metadata 和数据库现状生成迁移文件；只生成文件，不会改数据库
uv run alembic revision --autogenerate -m "message"

# 执行所有未应用的迁移，把数据库升级到最新版本
uv run alembic upgrade head

# 回滚上一个迁移版本，常用于验证 migration 是否可逆
uv run alembic downgrade -1
```

生成迁移后必须人工 review，重点确认字段类型、索引、comment、默认值和数据迁移逻辑。`CREATE_DB_TABLES` 只用于本地或测试快速初始化，生产环境不会在应用启动时自动建表。

## 文档地址

本地启动后访问：

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/api/v1/openapi.json`

## 校验和测试指令

安装 pre-commit hooks：

```bash
uv run pre-commit install
```

常用检查：

```bash
uv run ruff check app tests
uv run ruff format app tests
uv run pytest -q
uv run pre-commit run --all-files
```

如需启用 VS Code / Cursor 保存自动格式化，需要安装 Ruff 插件：
`https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff`

## 环境文件

- `.env.example`: 可提交的环境变量示例，用于说明项目需要哪些配置项。
- `.env`: 本地开发真实配置，从 `.env.example` 复制后自行修改，不提交到 Git。
- `.env.test`: 测试环境配置。
- `.env.prod`: 生产环境真实配置，不提交到 Git；生产部署也可以直接使用平台环境变量或 secrets 注入。

首次本地启动前先创建本地配置：

```bash
cp .env.example .env
```

`STATIC_DIR` 和 `LOG_DIR` 支持相对路径或绝对路径；相对路径会基于项目根目录解析。

默认按 `APP_ENV` 选择配置文件：

- `APP_ENV=local` -> `.env`
- `APP_ENV=test` -> `.env.test`
- `APP_ENV=production` -> `.env.prod`

应用调试行为由 `APP_ENV` 派生：只有 `APP_ENV=local` 时启用 FastAPI debug 和详细异常信息。

也可以显式指定：

```bash
ENV_FILE=.env.prod uv run uvicorn app.main:app
```

## 日志

项目使用 Loguru 统一处理日志：业务代码通过绑定名称的 Loguru logger 输出，SQLAlchemy 等第三方标准库 `logging` 记录通过 bridge 转发到 Loguru，Uvicorn 自身 server/access/asgi 日志在应用入口中关闭。日志格式统一包含时间、等级、模块和 request_id。业务 request/response 日志由中间件采集，日志同时输出到控制台和 `LOG_DIR` 对应目录下的 `app.log` / `error.log`。

默认 `LOG_LEVEL=INFO`，如需查看请求体、响应体和 SQL 调试日志，可设置 `LOG_LEVEL=DEBUG`，SQL 还需要 `SQL_ECHO=true`。

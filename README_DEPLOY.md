# 部署说明

## 推荐路线
- 代码托管：GitHub 私有仓库
- 后端部署：Render
- 数据库：Neon Postgres
- 文件存储：Supabase Storage

## 一次看懂上线顺序
1. 先整理仓库并推送到 GitHub
2. 在 Render 部署后端，先跑通 `/api/health`
3. 在 Neon 创建数据库并配置 `DATABASE_URL`
4. 执行数据库初始化和数据导入脚本
5. 验证登录、持仓、报告任务都能正常使用
6. 后续再把 `uploads/` 和 `reports/` 迁到 Supabase Storage

## 第 0 步：本地准备
确认本地已经具备这些文件：
- `.gitignore`
- `render.yaml`
- `requirements.txt`
- `.env.example`

本地不要提交这些内容：
- `.env`
- `logs/`
- `reports/`
- `uploads/`
- `quote_cache.json`
- `report_tasks.json`
- `report_index.json`
- `import_tasks.json`

## 第 1 步：推送到 GitHub
1. 创建 GitHub 私有仓库
2. 把当前项目推上去
3. 确认仓库里没有提交 `.env` 和本地缓存文件

## 第 2 步：在 Render 部署后端
当前后端入口是 `api_server:app`。

如果在 Render 手动配置：
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`

如果直接导入仓库：
- Render 会读取 [render.yaml](D:/Project/ZJ-MY-PROJECT/ji_jin/render.yaml)

## 第 3 步：配置 Render 环境变量
至少先配置这些变量：
- `LLM_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_FALLBACK_MODELS`
- `OPENAI_BASE_URL`
- `OPENAI_VISION_MODEL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_SSL`
- `EMAIL_FROM`

等数据库启用后再加：
- `DATABASE_URL`
- `DATA_BACKEND_STRICT`

等对象存储启用后再加：
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET_UPLOADS`
- `SUPABASE_STORAGE_BUCKET_REPORTS`
- `STORAGE_BACKEND_STRICT`

## 第 4 步：先做最小上线验证
Render 部署完成后，先访问：
- `/api/health`

预期：
- 服务可访问
- 返回 `status: ok`
- 未配置对象存储时，`storage.mode` 应为 `local`

这一步通过后，再把小程序里的 API 地址改成线上域名。

## 第 5 步：启用 Neon Postgres
在 Neon 创建数据库后，拿到 `DATABASE_URL`。

把它配置到：
- 本地 `.env`
- Render 环境变量

本地先验证：
- `/api/health` 返回里出现：
  - `data_backend: "postgres"`
  - `database.status: "ok"`
  - `storage_backend: "local"` 或 `storage_backend: "supabase"`

## 第 6 步：初始化数据库
拿到 `DATABASE_URL` 后，按这个顺序执行：

```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
.\.venv\Scripts\python.exe .\db_bootstrap.py
.\.venv\Scripts\python.exe .\db_seed_users.py
```

预期输出：
- `db_schema_applied`
- `seeded_users=...`
- `seeded_positions=...`

## 第 7 步：导入已有任务和报告索引
如果你希望把本地状态也迁进数据库，再执行：

```powershell
cd D:\Project\ZJ-MY-PROJECT\ji_jin
.\.venv\Scripts\python.exe .\db_seed_tasks.py
.\.venv\Scripts\python.exe .\db_seed_report_index.py
```

预期输出：
- `seeded_report_tasks=...`
- `seeded_import_tasks=...`
- `seeded_report_index_items=...`

## 第 8 步：验证数据库模式
完成上面步骤后，重点验证这些功能：
1. 登录
2. 修改密码
3. 持仓查询
4. 持仓增删改
5. 截图导入
6. 报告任务创建与查询
7. 报告列表和详情

## 第 9 步：小程序切线上域名
后端上线可用后：
1. 把小程序里的 API 地址改成 Render 域名
2. 在微信小程序后台把该域名加入合法 `request` 域名
3. 再完整回归一次登录、持仓、报告、导入流程

## 当前数据库迁移进度
已经具备：
- `database.py`：读取 `DATABASE_URL` 和数据库健康检查
- `db_schema.sql`：数据库表结构
- `db_user_repository.py`：用户/持仓数据库读写骨架
- `db_task_repository.py`：导入任务/报告任务数据库读写骨架
- `db_report_repository.py`：报告索引数据库读写骨架
- `db_bootstrap.py`：初始化表结构
- `db_seed_users.py`：导入用户与持仓
- `db_seed_tasks.py`：导入任务状态
- `db_seed_report_index.py`：导入报告索引
- `db_update_password.py`：按 `user_id` 更新数据库密码

## 当前还没迁走的部分
现在仍有本地文件依赖：
- `users.json` 作为回退
- `uploads/` 目录保存截图原图
- `reports/` 目录保存报告文件
- 本地索引/任务 JSON 作为回退

这意味着：
- 现在已经适合“自己用 + 小范围验证”
- 但还不算最终的多人正式版

## 下一阶段最值得做的事
建议按这个顺序继续：
1. 接入 Supabase Storage，迁走 `uploads/`
2. 再迁走 `reports/`
3. 最后再逐步弱化本地 JSON 回退

当前已完成第一步骨架：
- 截图上传已具备 `Supabase 优先、本地目录回退` 的保存设计
- 未配置 Supabase 时仍会继续写本地 `uploads/`
- 报告文件也已具备 `Supabase 优先、本地目录回退` 的保存设计
- 未配置 Supabase 时仍会继续写本地 `reports/`
- 如果要把旧报告批量补传到 Supabase，可执行：
  - `.\.venv\Scripts\python.exe .\db_backfill_report_storage.py`
- 如果要把旧导入任务里的本地绝对路径统一改成标准 URI，可执行：
  - `.\.venv\Scripts\python.exe .\db_normalize_import_task_paths.py`

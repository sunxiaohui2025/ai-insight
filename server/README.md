# InSight Cloud

深度收藏后端服务：用户认证、网页内容提取、全文翻译、分类管理和用量统计。

## 本地一键启动（开发）

在**项目根目录**启动后端 + 前端：

```bash
./start-all.sh    # 一键启动后端(:3002) + 前端(:3000)
./stop-all.sh     # 一键停止
```

后端配置读取 `server/.env.local`（数据库、端口 3002、管理员账号、LLM 地址等）。

## Docker / 生产部署

- 健康检查：`http://127.0.0.1:8000/health`
- 管理台：`http://127.0.0.1:8000/admin`
- OpenAPI：`http://127.0.0.1:8000/docs`

## Linux 原生部署（只需本目录）

将整个 `server` 目录上传到服务器，例如 `/opt/insight/server`。

```bash
chmod +x install.sh
./install.sh                     # 创建 .venv 并安装依赖
vim .env.local                   # 填写生产密钥、管理员账号、LLM 地址、端口
```

随后回到**项目根目录**用一键脚本启动（后端 + 前端）：

```bash
./start-all.sh
./stop-all.sh
```

生产环境建议使用 systemd：

```bash
sudo useradd --system --home /opt/insight --shell /usr/sbin/nologin insight
sudo chown -R insight:insight /opt/insight/server
sudo cp insight.service.example /etc/systemd/system/insight.service
sudo systemctl daemon-reload
sudo systemctl enable --now insight
sudo systemctl status insight
```

systemd 示例默认监听 `127.0.0.1:8000`，再由 Nginx/Caddy 提供 HTTPS 反向代理。服务器防火墙只开放 80/443，不要直接暴露 8000 或 vLLM 端口。

数据库备份：

```bash
./backup.sh /var/backups/insight
```

建议通过 cron 每日执行，并保留最近 7～30 天备份。`INSIGHT_DATABASE` 的父目录会在启动时自动创建。

## 公网部署

在服务器前放置 Caddy 或 Nginx，用域名申请 HTTPS 证书，并把请求反向代理至 `127.0.0.1:8000`。防火墙只公开 80/443，不公开 8000 和 vLLM 端口。将 Chrome 插件和 iOS 登录页中的服务器地址设置为 `https://你的域名`。

Docker 部署：

```bash
cp .env.example .env
chmod 600 .env
docker compose up -d --build
docker compose logs -f insight
```

`.env` 不会被 Dockerfile 打包进镜像，数据库保存在 Docker volume 中。

首次启动会根据 `INSIGHT_ADMIN_EMAIL` 和 `INSIGHT_ADMIN_PASSWORD` 创建管理员。普通用户注册后的状态为 `pending`，管理员在 `/admin` 批准后才能登录。

生产环境建议定期备份数据库文件。用户规模扩大后可将当前 SQLite 迁移到 PostgreSQL；API 和客户端数据结构无需改变。

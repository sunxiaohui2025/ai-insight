#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
command -v python3 >/dev/null || { echo "需要安装 Python 3" >&2; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
if [[ ! -f .env ]]; then cp .env.example .env; chmod 600 .env; echo "已创建 .env，请填写密钥和管理员配置。"; fi
echo "安装完成。请在项目根目录执行：./start-all.sh"

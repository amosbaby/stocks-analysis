#!/usr/bin/env bash

export VOLCES_API_KEY="fe1b0d9c-52a1-48ad-ba7d-caab97681998"
export VOLCES_MODEL="deepseek-v3-2-251201"
export VOLCES_ENDPOINT="https://ark.cn-beijing.volces.com/api/v3/chat/completions"

set -euo pipefail

# 在项目根目录执行，确保使用本项目的虚拟环境
cd "$(dirname "$0")"

source .venv/bin/activate
python stock-analysis/main.py

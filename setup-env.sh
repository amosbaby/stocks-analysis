#!/usr/bin/env bash
set -euo pipefail

LOCAL_PY_VER="3.13.5"
SERVER_PY_VER="3.10.13"
TARGET_ENV="${TARGET_ENV:-server}"
PY_VER="$SERVER_PY_VER"
PREFIX="/usr/local/python3.10"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"

if [[ "$TARGET_ENV" == "local" ]]; then
  echo ">>> 本地环境: Python ${LOCAL_PY_VER} (不在此脚本内安装)"
  exit 0
fi

echo ">>> 服务器环境: Python ${SERVER_PY_VER}"
echo ">>> Install build deps"
dnf groupinstall -y "Development Tools"
dnf install -y openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel xz-devel wget

echo ">>> Download Python ${PY_VER}"
cd /usr/local/src
wget -q https://www.python.org/ftp/python/${PY_VER}/Python-${PY_VER}.tgz
tar xf Python-${PY_VER}.tgz

echo ">>> Build and install Python ${PY_VER} to ${PREFIX}"
cd Python-${PY_VER}
./configure --enable-optimizations --prefix="${PREFIX}"
make -j"$(nproc)"
make altinstall

echo ">>> Verify Python"
"${PREFIX}/bin/python3.10" --version
"${PREFIX}/bin/python3.10" -m pip install -U pip setuptools wheel

echo ">>> Rebuild venv and install deps"
rm -rf "${VENV_DIR}"
"${PREFIX}/bin/python3.10" -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
python -m pip install -U pip setuptools wheel
pip install -r "${PROJECT_DIR}/requirements.txt"

echo ">>> Done"

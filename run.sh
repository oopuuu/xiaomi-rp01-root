#!/usr/bin/env bash
# ==============================================================================
# 小米 BE3600 Pro (RP01 / RP02) 一键 Root & 运维管理交互脚本 (macOS / Linux)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 检查 Python
if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
else
    echo "[-] 未找到 Python 环境！请先安装 Python (Python 2 或 Python 3 均可)。"
    exit 1
fi

# 启动交互式工具箱（无需预先强制安装任何第三方依赖，按需动态加载）
exec "$PY_BIN" "$SCRIPT_DIR/run.py" "$@"

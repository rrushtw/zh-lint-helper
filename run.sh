#!/bin/sh
# 在容器內跑 linter(宿主不裝 python,依 ~/.claude/CLAUDE.md 規範)。
# 用法: ./run.sh docs/**/*.md          掃指定檔
#       ./run.sh --test                 跑自我檢查
set -e
if [ "$1" = "--test" ]; then
  exec docker run --rm -v "$PWD":/w -w /w python:3.12-slim python test_lint.py
fi
exec docker run --rm -v "$PWD":/w -w /w python:3.12-slim python lint.py "$@"

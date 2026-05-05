#!/bin/bash
# Скрипт запуска тестов HR System
cd "$(dirname "$0")"
python -m pytest tests/ -v --tb=short "$@"

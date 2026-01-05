#!/bin/bash
set -euo pipefail

cd /app

# 默认使用生产配置，可通过外部覆盖
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-ops_job.settings.production}
export DJANGO_ENVIRONMENT=${DJANGO_ENVIRONMENT:-production}

echo "==> Running database migrations"

# 创建新的迁移
echo "==> Creating new migrations (if any):"
uv run manage.py makemigrations --verbosity=1

# 执行迁移，启用详细输出
echo "==> Applying migrations:"
uv run manage.py migrate --verbosity=1

# 验证迁移状态
echo "==> Migration status after apply:"
uv run manage.py showmigrations | grep -E "(accounts|hosts|job_templates|executor|script_templates|quick_execute|scheduler|permissions|dashboard|system_config|agents)" | tail -20

# 收集静态文件（可通过 SKIP_COLLECTSTATIC=1 跳过）
if [[ -z "${SKIP_COLLECTSTATIC:-}" ]]; then
  echo "==> Collecting static files"
  uv run manage.py collectstatic --noinput
else
  echo "==> Skipping collectstatic (SKIP_COLLECTSTATIC set)"
fi

# 可选初始化管理员
if [[ -n "${INIT_ADMIN_USERNAME:-}" && -n "${INIT_ADMIN_PASSWORD:-}" ]]; then
  INIT_ADMIN_NICKNAME=${INIT_ADMIN_NICKNAME:-Admin}
  INIT_ADMIN_IS_SUPER=${INIT_ADMIN_IS_SUPER:-true}
  echo "==> Creating/updating admin user ${INIT_ADMIN_USERNAME}"
  uv run manage.py manage_user add -u "${INIT_ADMIN_USERNAME}" -p "${INIT_ADMIN_PASSWORD}" -n "${INIT_ADMIN_NICKNAME}" $( [[ "${INIT_ADMIN_IS_SUPER,,}" == "true" ]] && echo "-s" )
fi

echo "==> Starting supervisord"
exec /usr/bin/supervisord -c /docker/supervisor.conf

#!/bin/sh
# Apply database migrations (unless disabled) and then run the given command.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "entrypoint: applying database migrations"
    alembic upgrade head
fi

exec "$@"

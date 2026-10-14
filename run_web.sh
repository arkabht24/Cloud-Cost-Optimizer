#!/usr/bin/env zsh
# Local React dashboard. Start run_api.sh in another terminal first.
cd "${0:A:h}/web"
exec npm run dev -- --host 127.0.0.1 --port 5173

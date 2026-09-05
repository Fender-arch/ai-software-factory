# GitHub Actions secrets for VPS deploy
#
# Fill these in the repo: Settings → Secrets and variables → Actions
# Placeholders are SET_ME so the names exist; replace before running "Deploy VPS".
#
# Required (you asked to fill these first):
#   VPS_HOST            IPv4/IPv6 of the VPS
#   VPS_USER            SSH user (root or a sudoer in the docker group)
#   VPS_PASSWORD        SSH password (also used for sudo -S if needed)
#   DOMAIN_MINIAPP      Public hostname for Telegram Mini App (A/AAAA → VPS_HOST)
#   DOMAIN_CONSOLE      Public hostname for owner TZ console (can equal DOMAIN_MINIAPP)
#
# Required for a working production stack:
#   POSTGRES_PASSWORD   Strong password (not asf/asf). Alphanumeric recommended
#   CONSOLE_TOKEN       Shared token for /console/ (X-Console-Token)
#   TELEGRAM_BOT_TOKEN  From @BotFather
#   OWNER_TELEGRAM_ID   Owner Telegram numeric id (HITL)
#   GROQ_API_KEY        Server STT (and optional LLM)
#   LETSENCRYPT_EMAIL   For certbot HTTPS on the two ASF domains only
#
# Optional:
#   VPS_SSH_PORT        Default 22
#   VPS_DEPLOY_PATH     Default /opt/asf
#   ASF_HOST_PORT       Default 18000 (localhost only; never 80/443)
#   OPENAI_API_KEY      Only if STT_PROVIDER=whisper
#   STT_PROVIDER        Default groq
#   STT_MODEL           Default whisper-large-v3-turbo
#   LLM_PROVIDER        Default stub (set groq to enable LLM-driven Discovery)
#   LLM_MODEL
#   DISCOVERY_ENGINE    auto | llm | fsm (default auto = llm when LLM_PROVIDER is not stub)
#   ASF_ESTIMATE_HOURLY_RATE  Owner TZ cost heuristic (default 3000)
#   ASF_ESTIMATE_CURRENCY     Currency for that estimate (default RUB)
#   ASF_INTERVENTION_KEY      Seals Intervention Queue secrets (DEC-013)
#   ASF_INTERVENTION_TTL_HOURS  Default 72
#   CURSOR_API_KEY            Optional Cursor Cloud Agent
#   CURSOR_CLOUD_API_URL      Default https://api.cursor.com
#   CURSOR_AGENT_REPO         Optional repo URL for the agent

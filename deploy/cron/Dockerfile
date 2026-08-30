# Build context for the `pumasi-sign-cron` Railway service — a tiny
# curl-only container whose only job is to POST /api/jobs/daily once a day
# (see railway.json's cronSchedule) with the shared X-Job-Token secret.
#
# See ../README.md for how this was originally provisioned and how to
# redeploy it (`railway up` from this directory).
FROM curlimages/curl:8.11.1
USER root
ENTRYPOINT ["sh", "-c", "curl -sS -X POST \"$APP_BASE_URL/api/jobs/daily\" -H \"X-Job-Token: $JOB_TOKEN\" -w '\\nHTTP %{http_code}\\n' -f"]

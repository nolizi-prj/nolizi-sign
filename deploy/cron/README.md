# `pumasi-sign-cron` Railway service

Build context for the `pumasi-sign-cron` service (project `pumasi-sign`),
which calls `POST /api/jobs/daily` once a day per `railway.json`'s
`cronSchedule` (`0 9 * * *`, UTC).

To (re)deploy, from the repo root:

```
railway up deploy/cron --path-as-root --service pumasi-sign-cron --detach
```

`--path-as-root` is required: without it the Railway CLI archives the whole
linked repo root, so the service would build the app's root `Dockerfile`
(and apply the root `railway.json`, including its `/api/health` healthcheck)
instead of this directory's curl-only image — the container then crashes on
boot because this service has no `DATABASE_URL`. Likewise always pass
`--service` explicitly; the CLI's linked service is whatever was linked
last and `railway up` will happily deploy the wrong image to it.

The service's `APP_BASE_URL`/`JOB_TOKEN` variables are already set on the
service as Railway reference variables pointing at the main `pumasi-sign`
service's own values — nothing to configure here.

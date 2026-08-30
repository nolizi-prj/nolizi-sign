"""``POST /api/jobs/daily`` — the single daily cron entrypoint (Task 12 wires the scheduler).

Authenticated by a shared secret header (``X-Job-Token``) rather than a
user session, since the caller is an external scheduler, not a browser.
Runs three independent pieces of work and never lets one's failure hide the
others:

1. ``notifications.run_daily_reminders`` — reminder emails for every
   eligible submitter across all pending submissions (mail failures are
   swallowed inside ``mailer.send``/``notifications``, never raised here).
2. A database dump (``pg_dump -Fc``) and a tar of the data directory
   (excluding ``backups/`` itself), each pruned to the newest 14 by
   filename sort (``YYYYMMDD`` sorts chronologically as a string).
3. A SharePoint archive sweep over every completed submission that isn't
   archived yet, retrying completion-time failures and backfilling
   envelopes completed before the archive feature shipped. Skipped
   entirely (reported as ``0``/``0``) when ``SP_DRIVE_ID`` is unset.

Both backup steps are best-effort: a missing ``pg_dump`` binary or any
backup failure is logged and reflected as ``False`` in the response, not
raised — this endpoint always returns 200 (given a valid token) so a
partial failure is visible in the response body instead of aborting the
whole job (e.g. skipping reminders because backups aren't set up yet, or
vice versa). The archive sweep is best-effort in the same way:
``archive_submission`` never raises, and one submission's failure doesn't
stop the sweep from attempting the rest.
"""

import hmac
import logging
import os
import shutil
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications, sharepoint
from app.auth import get_settings
from app.config import Settings
from app.db import get_db
from app.models import Submission
from app.storage import get_storage

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

KEEP_BACKUPS = 14
PG_DUMP_TIMEOUT_SECONDS = 600


def _require_job_token(x_job_token: str | None, settings: Settings) -> None:
    """Raise 403 unless ``settings.job_token`` is non-empty and matches the header exactly.

    Uses ``hmac.compare_digest`` for the comparison rather than ``!=``: a
    naive string comparison short-circuits on the first mismatched
    character, so its running time leaks how many leading characters of a
    guess were correct — an attacker with network access to this endpoint
    could exploit that timing signal to brute-force the token one character
    at a time. ``compare_digest`` always takes the same time regardless of
    where (or whether) the strings differ.
    """
    if not settings.job_token or not hmac.compare_digest(x_job_token or "", settings.job_token):
        raise HTTPException(status_code=403, detail="Forbidden")


def _pg_connection_params(database_url: str) -> dict[str, str]:
    """Parse ``database_url`` (SQLAlchemy ``dialect+driver://`` form) into discrete pg_dump params.

    ``Settings.database_url`` is written SQLAlchemy-style (e.g.
    ``postgresql+psycopg://user:pass@host:port/db``, see ``tests/conftest.py``'s
    ``TEST_DATABASE_URL``); ``urlsplit`` parses the netloc/path correctly
    regardless of the ``+driver`` suffix on the scheme, so no separate
    scheme-stripping step is needed. Values are percent-decoded since a
    password/user containing reserved URL characters would otherwise be
    passed to ``pg_dump`` still escaped.
    """
    parsed = urlsplit(database_url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": unquote(parsed.username) if parsed.username else "",
        "password": unquote(parsed.password) if parsed.password else "",
        "dbname": parsed.path.lstrip("/"),
    }


def _backup_database(settings: Settings, backups_dir: Path, date_str: str) -> bool:
    """Write a ``pg_dump -Fc`` of ``settings.database_url`` to ``backups_dir``. Returns success.

    The database password is **never** passed as a command-line argument:
    process argv is visible to any local user via ``ps``/``/proc/<pid>/cmdline``,
    and (before this was fixed) a full credential-bearing URL there also
    ended up embedded verbatim in ``subprocess.CalledProcessError``'s
    message — and therefore in our own logs — on any ``pg_dump`` failure.
    Instead, the URL is parsed into discrete ``-h``/``-p``/``-U``/dbname
    arguments, and the password is passed only via ``PGPASSWORD`` in a
    *copy* of the environment scoped to this one subprocess call (``env=``
    is a new dict built from ``os.environ``, never a mutation of our own
    process's environment). On failure, only the exit code and a
    length-capped stderr are logged — never the command list itself — as a
    second line of defense against ever reintroducing a credential leak
    here.

    A hung ``pg_dump`` (e.g. a stalled connection) is bounded by
    ``PG_DUMP_TIMEOUT_SECONDS`` so a single bad run can't block the daily
    job indefinitely; a timeout is treated the same as any other backup
    failure (logged, ``False`` returned, the rest of the job continues).
    """
    pg_dump = shutil.which("pg_dump")
    if pg_dump is None:
        logger.warning("pg_dump not found on PATH; skipping database backup")
        return False

    params = _pg_connection_params(settings.database_url)
    dest = backups_dir / f"db-{date_str}.dump"
    command = [
        pg_dump,
        "-h",
        params["host"],
        "-p",
        params["port"],
        "-U",
        params["user"],
        "-Fc",
        "-f",
        str(dest),
        params["dbname"],
    ]
    env = {**os.environ, "PGPASSWORD": params["password"]}

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            env=env,
            timeout=PG_DUMP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.error("pg_dump backup timed out after %ds", PG_DUMP_TIMEOUT_SECONDS)
        return False
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace")[:2000] if exc.stderr else ""
        logger.error("pg_dump backup failed (exit code %s); stderr: %s", exc.returncode, stderr)
        return False
    except OSError:
        logger.exception("pg_dump backup failed to start")
        return False
    return True


def _backup_files(settings: Settings, backups_dir: Path, date_str: str) -> bool:
    """Tar ``settings.data_dir`` (excluding ``backups/``) to ``backups_dir``. Returns success."""
    data_dir = Path(settings.data_dir)
    dest = backups_dir / f"files-{date_str}.tar"
    try:
        with tarfile.open(dest, "w") as tar:
            for path in data_dir.rglob("*"):
                if path.is_dir():
                    continue
                relative = path.relative_to(data_dir)
                if relative.parts[0] == "backups":
                    continue
                tar.add(path, arcname=relative.as_posix())
    except OSError:
        logger.exception("Files backup failed")
        return False
    return True


def _prune(backups_dir: Path, pattern: str, keep: int) -> None:
    """Delete all but the newest ``keep`` files matching ``pattern``, newest determined by filename sort."""
    files = sorted(backups_dir.glob(pattern))
    for stale in files[: max(0, len(files) - keep)]:
        stale.unlink(missing_ok=True)


def _archive_sweep(db: Session, settings: Settings) -> tuple[int, int]:
    """Archive every completed-but-unarchived submission. Returns (archived, failed).

    Retry for completion-time failures and backfill for envelopes completed
    before this feature shipped (their ``archived_at`` is NULL). Skipped
    entirely when ``SP_DRIVE_ID`` is unset so a disabled feature doesn't
    log a failure per envelope every day. Best-effort like the backup
    steps: ``archive_submission`` never raises, and one failure doesn't
    stop the sweep.
    """
    if not settings.sp_drive_id:
        return 0, 0

    storage = get_storage(settings)
    pending = db.scalars(
        select(Submission).where(
            Submission.status == "completed",
            Submission.archived_at.is_(None),
            Submission.signed_pdf_key.is_not(None),
        ),
    ).all()

    archived = failed = 0
    for submission in pending:
        if sharepoint.archive_submission(db, submission, storage, settings):
            archived += 1
        else:
            failed += 1
    return archived, failed


@router.post("/daily")
def run_daily_job(
    x_job_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Expire past-due envelopes, warn on approaching deadlines, send due
    reminders, back up the database and data directory, then sweep SharePoint
    archives.

    Returns ``{"reminders_sent": int, "expired": int, "expiry_warnings": int,
    "backup": {"db": bool, "files": bool}, "archived": int,
    "archive_failed": int}``.
    """
    _require_job_token(x_job_token, settings)

    # Expirations run first so a just-expired envelope isn't also reminded
    # about (the reminder query only sees still-pending submissions).
    expired = notifications.run_expirations(db, settings)
    db.commit()
    expiry_warnings = notifications.send_expiry_warnings(db, settings)
    db.commit()

    reminders_sent = notifications.run_daily_reminders(db, settings)
    db.commit()

    date_str = datetime.now(UTC).strftime("%Y%m%d")
    backups_dir = Path(settings.data_dir) / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    db_ok = _backup_database(settings, backups_dir, date_str)
    files_ok = _backup_files(settings, backups_dir, date_str)

    _prune(backups_dir, "db-*.dump", KEEP_BACKUPS)
    _prune(backups_dir, "files-*.tar", KEEP_BACKUPS)

    archived, archive_failed = _archive_sweep(db, settings)

    return {
        "reminders_sent": reminders_sent,
        "expired": expired,
        "expiry_warnings": expiry_warnings,
        "backup": {"db": db_ok, "files": files_ok},
        "archived": archived,
        "archive_failed": archive_failed,
    }

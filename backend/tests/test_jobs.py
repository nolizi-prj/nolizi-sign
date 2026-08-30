"""Tests for POST /api/jobs/daily: the X-Job-Token gate, reminder side effects, and backups.

Mail delivery is never explicitly mocked here — ``app_settings``/the
settings built by ``_settings`` below leave ``ms_*``/``mail_sender`` unset,
so ``mailer.send`` short-circuits to ``False`` without any network call
(see test_mailer.py's ``test_send_returns_false_without_any_network_call_when_not_configured``);
that's the seam this suite relies on rather than monkeypatching
``notifications``/``mailer`` directly, since what's under test here is the
job's token gate, its reminder *count*, and its backup file side effects —
not delivery.
"""

import os
import subprocess
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app import sharepoint
from app.config import Settings
from app.models import Submission, Submitter, Template, User
from app.routers import jobs

TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test"


def _settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "job_token": "test-job-token",
        "data_dir": str(tmp_path),
        "database_url": TEST_DATABASE_URL,
        "app_base_url": "http://testserver",
    }
    base.update(overrides)
    return Settings(**base)


# --- token gate -------------------------------------------------------------


def test_daily_job_without_token_header_is_403(make_client, tmp_path: Path) -> None:
    client = make_client(_settings(tmp_path))
    resp = client.post("/api/jobs/daily")
    assert resp.status_code == 403


def test_daily_job_with_wrong_token_is_403(make_client, tmp_path: Path) -> None:
    client = make_client(_settings(tmp_path))
    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "wrong"})
    assert resp.status_code == 403


def test_daily_job_rejects_even_matching_empty_token_when_unconfigured(make_client, tmp_path: Path) -> None:
    client = make_client(_settings(tmp_path, job_token=""))
    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": ""})
    assert resp.status_code == 403


# --- side effects -------------------------------------------------------------


def test_daily_job_with_correct_token_runs_reminders_and_returns_expected_shape(
    make_client,
    tmp_path: Path,
    db: Session,
) -> None:
    settings = _settings(tmp_path)
    client = make_client(settings)

    now = datetime.now(UTC)
    sender = User(email="sender@example.com", name="Sender")
    db.add(sender)
    db.flush()
    template = Template(
        name="Doc",
        created_by=sender.id,
        original_file_key="x",
        pdf_key="x",
        page_count=1,
        fields=[
            {
                "id": "f1",
                "type": "signature",
                "role": "Signer 1",
                "page": 0,
                "x": 0.1,
                "y": 0.1,
                "w": 0.1,
                "h": 0.1,
                "required": True,
            },
        ],
    )
    db.add(template)
    db.flush()
    signer = User(email="signer@example.com", name="Signer")
    db.add(signer)
    db.flush()
    submission = Submission(
        template_id=template.id,
        title="Contract",
        status="pending",
        created_by=sender.id,
        created_at=now - timedelta(days=4),
    )
    db.add(submission)
    db.flush()
    submitter = Submitter(submission_id=submission.id, user_id=signer.id, role="Signer 1", status="pending")
    db.add(submitter)
    db.commit()

    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "test-job-token"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reminders_sent"] == 1
    assert set(body["backup"]) == {"db", "files"}
    assert isinstance(body["backup"]["db"], bool)
    assert isinstance(body["backup"]["files"], bool)

    db.refresh(submitter)
    assert submitter.reminder_count == 1
    assert submitter.last_reminded_at is not None


def test_daily_job_with_no_eligible_submitters_reports_zero(make_client, tmp_path: Path) -> None:
    client = make_client(_settings(tmp_path))
    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "test-job-token"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["reminders_sent"] == 0


# --- backup helpers (direct unit tests, deterministic re: pg_dump presence) --------------


def test_backup_database_skips_and_returns_false_when_pg_dump_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(jobs.shutil, "which", lambda name: None)
    settings = _settings(tmp_path)
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    ok = jobs._backup_database(settings, backups_dir, "20260730")

    assert ok is False
    assert not (backups_dir / "db-20260730.dump").exists()


def test_backup_files_creates_tar_excluding_backups_dir(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "a.pdf").write_bytes(b"hello")
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    (backups_dir / "old.dump").write_bytes(b"junk")

    ok = jobs._backup_files(settings, backups_dir, "20260730")

    assert ok is True
    tar_path = backups_dir / "files-20260730.tar"
    assert tar_path.exists()
    with tarfile.open(tar_path) as tar:
        names = tar.getnames()
    assert "templates/a.pdf" in names
    assert not any(name.startswith("backups") for name in names)


def test_prune_keeps_only_newest_n_by_filename_sort(tmp_path: Path) -> None:
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    for i in range(1, 17):
        (backups_dir / f"db-202601{i:02d}.dump").write_bytes(b"x")

    jobs._prune(backups_dir, "db-*.dump", 14)

    remaining = sorted(p.name for p in backups_dir.glob("db-*.dump"))
    assert len(remaining) == 14
    assert remaining[0] == "db-20260103.dump"
    assert remaining[-1] == "db-20260116.dump"


def test_prune_is_a_no_op_when_under_the_limit(tmp_path: Path) -> None:
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    (backups_dir / "db-20260101.dump").write_bytes(b"x")

    jobs._prune(backups_dir, "db-*.dump", 14)

    assert (backups_dir / "db-20260101.dump").exists()


def test_pg_connection_params_parses_url_and_decodes_credentials() -> None:
    params = jobs._pg_connection_params("postgresql+psycopg://myuser:s3cr%40t@dbhost:5433/mydb")
    assert params == {
        "host": "dbhost",
        "port": "5433",
        "user": "myuser",
        "password": "s3cr@t",
        "dbname": "mydb",
    }


def test_pg_connection_params_defaults_host_and_port() -> None:
    params = jobs._pg_connection_params("postgresql://u:p@/mydb")
    assert params["host"] == "localhost"
    assert params["port"] == "5432"


# --- credential-safety / timeout regression coverage -------------------------------------


def test_backup_database_never_passes_password_via_argv(tmp_path: Path, monkeypatch) -> None:
    """The password must never appear in the argv list passed to subprocess.run."""
    monkeypatch.setattr(jobs.shutil, "which", lambda name: "/usr/bin/pg_dump")
    settings = _settings(tmp_path, database_url="postgresql+psycopg://myuser:s3cr3t-password@dbhost:5433/mydb")
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        captured["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)

    ok = jobs._backup_database(settings, backups_dir, "20260730")

    assert ok is True
    assert all("s3cr3t-password" not in str(part) for part in captured["command"])
    assert "myuser" in captured["command"]
    assert "dbhost" in captured["command"]
    assert "-U" in captured["command"]
    assert "-h" in captured["command"]
    # The password is only ever delivered via PGPASSWORD in the subprocess's env.
    assert captured["env"]["PGPASSWORD"] == "s3cr3t-password"
    assert captured["timeout"] == jobs.PG_DUMP_TIMEOUT_SECONDS


def test_backup_database_env_is_a_copy_and_does_not_leak_into_our_own_process(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(jobs.shutil, "which", lambda name: "/usr/bin/pg_dump")
    settings = _settings(tmp_path, database_url="postgresql+psycopg://u:p@h:5432/d")
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()
    monkeypatch.setattr(
        jobs.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
    )

    assert "PGPASSWORD" not in os.environ
    jobs._backup_database(settings, backups_dir, "20260730")
    assert "PGPASSWORD" not in os.environ


def test_backup_database_called_process_error_does_not_log_the_command_or_password(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.setattr(jobs.shutil, "which", lambda name: "/usr/bin/pg_dump")
    settings = _settings(tmp_path, database_url="postgresql+psycopg://myuser:s3cr3t-password@dbhost:5433/mydb")
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=command, stderr=b"connection refused")

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)

    with caplog.at_level("ERROR"):
        ok = jobs._backup_database(settings, backups_dir, "20260730")

    assert ok is False
    assert "s3cr3t-password" not in caplog.text


def test_backup_database_timeout_is_treated_as_a_failure_not_raised(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(jobs.shutil, "which", lambda name: "/usr/bin/pg_dump")
    settings = _settings(tmp_path)
    backups_dir = tmp_path / "backups"
    backups_dir.mkdir()

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)

    ok = jobs._backup_database(settings, backups_dir, "20260730")

    assert ok is False


# --- archive sweep -------------------------------------------------------------


def _archive_rows(db: Session) -> tuple[int, int, int, int]:
    """Insert 4 submissions: two archive-eligible, one already archived, one pending."""
    owner = User(email="owner@pumasi.ai", name="Owner")
    db.add(owner)
    db.flush()
    template = Template(name="Doc", created_by=owner.id, original_file_key="x", pdf_key="x", page_count=1)
    db.add(template)
    db.flush()
    now = datetime.now(UTC)

    def _submission(**overrides) -> Submission:
        base = dict(template_id=template.id, title="T", created_by=owner.id, status="completed", completed_at=now)
        base.update(overrides)
        submission = Submission(**base)
        db.add(submission)
        return submission

    eligible_a = _submission(signed_pdf_key="s/a.pdf")
    eligible_b = _submission(signed_pdf_key="s/b.pdf")
    already = _submission(signed_pdf_key="s/c.pdf", archived_at=now, archive_url="u")
    pending = _submission(status="pending", completed_at=None)
    db.commit()
    return eligible_a.id, eligible_b.id, already.id, pending.id


def test_daily_job_sweeps_unarchived_completed_submissions(
    make_client,
    tmp_path: Path,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(_settings(tmp_path, sp_drive_id="drive-1"))
    eligible_a, eligible_b, _already, _pending = _archive_rows(db)

    attempted: list[int] = []

    def fake_archive(db_: object, submission: Submission, storage: object, settings: object) -> bool:
        attempted.append(submission.id)
        return submission.id == eligible_a  # one success, one failure

    monkeypatch.setattr(sharepoint, "archive_submission", fake_archive)

    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "test-job-token"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["archived"] == 1
    assert body["archive_failed"] == 1
    assert sorted(attempted) == sorted([eligible_a, eligible_b])


def test_daily_job_skips_sweep_when_disabled(
    make_client,
    tmp_path: Path,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(_settings(tmp_path))  # sp_drive_id left empty
    _archive_rows(db)

    def must_not_be_called(*args: object, **kwargs: object) -> bool:
        raise AssertionError("archive_submission must not be called when SP_DRIVE_ID is unset")

    monkeypatch.setattr(sharepoint, "archive_submission", must_not_be_called)

    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "test-job-token"})

    assert resp.status_code == 200
    assert resp.json()["archived"] == 0
    assert resp.json()["archive_failed"] == 0

"""Application configuration, read from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings sourced from environment variables.

    Every field has a default so the app can be imported and instantiated
    without any environment variables set (e.g. during tooling, migrations
    tests, or local development bootstrap).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ms_tenant_id: str = ""
    ms_client_id: str = ""
    ms_client_secret: str = ""
    mail_sender: str = ""
    session_secret: str = ""
    admin_emails: str = ""
    allowed_email_domains: str = "pumasi.ai"
    job_token: str = ""
    database_url: str = ""
    data_dir: str = "/data"
    app_base_url: str = ""
    feedback_email: str = "legal@pumasi.ai"
    dev_auth_bypass: bool = False
    sp_drive_id: str = ""
    sp_archive_folder: str = "Signed_document_archive"
    # Convert docx/doc/pptx/ppt with Word/PowerPoint's own rendering via Graph
    # (upload to SP_DRIVE_ID temp folder → ?format=pdf → delete), falling
    # back to LibreOffice on any failure. Requires sp_drive_id + Graph creds.
    graph_convert: bool = False

    @property
    def admin_emails_list(self) -> list[str]:
        """Return ADMIN_EMAILS as a list of lowercased, trimmed email addresses."""
        return [email.strip().lower() for email in self.admin_emails.split(",") if email.strip()]

    @property
    def allowed_email_domains_list(self) -> list[str]:
        """Return ALLOWED_EMAIL_DOMAINS as lowercased, trimmed domain names."""
        return [domain.strip().lower() for domain in self.allowed_email_domains.split(",") if domain.strip()]

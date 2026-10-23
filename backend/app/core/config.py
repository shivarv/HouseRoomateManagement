from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


def _with_psycopg_driver(url: str) -> str:
    """Neon (and most providers) hand out `postgresql://` URLs; SQLAlchemy needs the driver name."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    # App traffic. On Neon this is the pooled (-pooler, PgBouncer) connection string.
    database_url: str = "postgresql+psycopg://roommate:roommate@localhost:5434/roommate"
    # Neon's direct connection string, used for migrations (`neon env pull` writes both).
    database_url_unpooled: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    jwt_secret: str = "change-me"
    access_token_expire_minutes: int = 60 * 24 * 7
    # Where invite links in emails point (the web app).
    web_url: str = "http://localhost:5173"
    # Invite emails go out through Resend (https://resend.com) when a key is set; without one,
    # invites are still saved and the web app opens the sender's own email app instead.
    resend_api_key: str | None = None
    # Or through Brevo (https://brevo.com); used instead of Resend when set.
    brevo_api_key: str | None = None
    email_from: str = "Roommates <onboarding@resend.dev>"

    @field_validator("database_url", "database_url_unpooled")
    @classmethod
    def _driver(cls, value: str | None) -> str | None:
        return _with_psycopg_driver(value) if value else value

    @property
    def uses_pgbouncer(self) -> bool:
        return "-pooler." in self.database_url

    @property
    def migration_url(self) -> str:
        """Migrations need a direct connection: PgBouncer's transaction mode drops session state."""
        if self.uses_pgbouncer and self.database_url_unpooled:
            return self.database_url_unpooled
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    archivum_db_path: str = "data/archivum.db"

    ao3_username: str = ""
    ao3_password: str = ""
    ao3_contact_email: str = ""
    ao3_min_delay_seconds: float = 4.0
    ao3_max_requests_per_session: int = 500

    @property
    def db_path(self) -> Path:
        path = Path(self.archivum_db_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def sqlalchemy_database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def archivo_dir(self) -> Path:
        return BASE_DIR / "data" / "archivo"


settings = Settings()

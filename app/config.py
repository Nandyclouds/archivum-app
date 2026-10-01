from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    archivum_db_path: str = "data/archivum.db"

    # Vacío = sin auth (uso local, ya restringido por red/Tailscale). Con un
    # valor puesto, todo /api/* lo exige (header o query param) — necesario
    # en cuanto la app queda expuesta en un dominio público (ver main.py).
    archivum_auth_token: str = ""

    ao3_username: str = ""
    ao3_password: str = ""
    ao3_contact_email: str = ""
    ao3_min_delay_seconds: float = 4.0
    ao3_max_requests_per_session: int = 500

    # Clave simétrica (Fernet) para cifrar la contraseña de AO3 de cada
    # cuenta antes de guardarla (ver app/crypto.py, Cuenta.ao3_password_encriptada).
    # Generarla una sola vez con Fernet.generate_key() y ponerla en .env.
    archivum_encryption_key: str = ""

    # Para el mail de aviso cuando "Revisar WIPs" encuentra capítulo nuevo o
    # un fic completado (ver app/api/routers/sync.py) — se manda a la
    # dirección con la que cada cuenta se registró. Opcional: sin estas dos,
    # el aviso no se manda y el sync sigue funcionando igual.
    gmail_address: str = ""
    gmail_app_password: str = ""

    @property
    def db_path(self) -> Path:
        """Base de datos de un solo tenant: la usa app/cli.py (herramienta
        de desarrollo local, sin cuentas) y el script que migró esos datos
        a la cuenta 1. La API web usa user_db_path(cuenta_id)."""
        path = Path(self.archivum_db_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def sqlalchemy_database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def archivo_dir_legado(self) -> Path:
        """Para app/cli.py y guardar_snapshot_html cuando no se le pasa un
        archivo_dir explícito — mismo criterio que db_path arriba."""
        return BASE_DIR / "data" / "archivo"

    @property
    def control_db_path(self) -> Path:
        return BASE_DIR / "data" / "control.db"

    def user_data_dir(self, cuenta_id: int) -> Path:
        return BASE_DIR / "data" / "users" / str(cuenta_id)

    def user_db_path(self, cuenta_id: int) -> Path:
        return self.user_data_dir(cuenta_id) / "archivum.db"

    def archivo_dir(self, cuenta_id: int) -> Path:
        return self.user_data_dir(cuenta_id) / "archivo"

    def perfil_dir(self, cuenta_id: int) -> Path:
        return self.user_data_dir(cuenta_id) / "perfil"

    def emojis_dir(self, cuenta_id: int) -> Path:
        return self.user_data_dir(cuenta_id) / "emojis"

    def resenas_dir(self, cuenta_id: int) -> Path:
        return self.user_data_dir(cuenta_id) / "resenas"


settings = Settings()

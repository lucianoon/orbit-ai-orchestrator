from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    redis_url: str = Field("redis://localhost:6379/1", env="REDIS_URL")
    executor_queue: str = Field("executor-tasks", env="EXECUTOR_QUEUE")
    planner_model: str = Field("gpt-4.1", env="PLANNER_MODEL")
    verifier_model: str = Field("gpt-4.1", env="VERIFIER_MODEL")
    max_fanout: int = Field(8, env="MAX_FANOUT")
    poll_interval: float = Field(0.2, env="POLL_INTERVAL")
    poll_max_seconds: int = Field(180, env="POLL_MAX_SECONDS")
    cors_origins: str = Field("http://localhost:3000", env="CORS_ORIGINS")
    data_dir: str = Field(str(BASE_DIR / "data"), env="APP_DATA_DIR")
    history_db_path: str = Field(str(BASE_DIR / "data" / "orbit_history.db"), env="HISTORY_DB_PATH")
    auth_db_path: str = Field(str(BASE_DIR / "data" / "orbit_auth.db"), env="AUTH_DB_PATH")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

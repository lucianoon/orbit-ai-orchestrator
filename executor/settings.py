from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = Field("redis://localhost:6379/1", env="REDIS_URL")
    executor_queue: str = Field("executor-tasks", env="EXECUTOR_QUEUE")
    searx_url: str = Field("http://localhost:8080", env="SEARX_URL")
    playwright_ws: str | None = Field(None, env="PLAYWRIGHT_WS")
    code_timeout: int = Field(15, env="CODE_TIMEOUT")
    code_mem_mb: int = Field(256, env="CODE_MEM_MB")
    code_fsize_mb: int = Field(10, env="CODE_FSIZE_MB")
    
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()

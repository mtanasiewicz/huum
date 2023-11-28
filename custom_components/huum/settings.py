from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    huum_username: Optional[str]
    huum_password: Optional[str]


settings = Settings()

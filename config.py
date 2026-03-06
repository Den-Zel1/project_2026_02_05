from dotenv import load_dotenv
from pydantic.v1 import BaseSettings

load_dotenv()

PUBLIC_URLS = (
    "/login",
    "/docs",
    "/",
    "/register",
    "/auth",
    "/openapi.json",
    "/redoc",
    "/static"
)


class Settings(BaseSettings):
    DB_DRIVER: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    PROJECT_NAME: str
    SECRET_KEY: str
    ALGORITHM: str
    TOKEN_EXPIRE_MINUTES: int


settings = Settings()

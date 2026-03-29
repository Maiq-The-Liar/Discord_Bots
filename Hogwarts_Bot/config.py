import os
from dataclasses import dataclass
from dotenv import load_dotenv

env_file = os.getenv("ENV_FILE", ".env")
load_dotenv(env_file, override=True)


@dataclass(frozen=True)
class Settings:
    discord_token: str
    guild_id: int
    database_path: str


def load_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    guild_id = os.getenv("GUILD_ID", "").strip()
    db_path = os.getenv("DATABASE_PATH", "hogwarts_bot.db").strip()

    if not token:
        raise ValueError("Missing DISCORD_TOKEN in environment.")

    if not guild_id:
        raise ValueError("Missing GUILD_ID in environment.")

    return Settings(
        discord_token=token,
        guild_id=int(guild_id),
        database_path=db_path,
    )
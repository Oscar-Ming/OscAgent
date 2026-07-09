from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    env: str = Field(default="development", alias="OSCAGENT_ENV")
    model: str = Field(default="openai:gpt-4.1-mini", alias="OSCAGENT_MODEL")
    db_path: Path = Field(default=Path("data/oscagent.db"), alias="OSCAGENT_DB_PATH")

    discord_bot_token: str | None = Field(default=None, alias="DISCORD_BOT_TOKEN")
    discord_guild_id: str | None = Field(default=None, alias="DISCORD_GUILD_ID")
    discord_proxy: str | None = Field(default=None, alias="DISCORD_PROXY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    llm_proxy: str | None = Field(default=None, alias="LLM_PROXY")

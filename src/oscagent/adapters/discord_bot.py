from __future__ import annotations

import asyncio
import socket

from oscagent.config import Settings
from oscagent.discord_core import DiscordCommandHandler
from oscagent.llm import MockLLMProvider


def run_discord_bot(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required to run the Discord bot.")

    asyncio.run(_run_discord_bot(settings))


async def _run_discord_bot(settings: Settings) -> None:
    try:
        import aiohttp
        import discord
        from discord import app_commands
    except ImportError as exc:
        raise RuntimeError(
            'Discord support is not installed. Run: python -m pip install -e ".[discord]"'
        ) from exc

    intents = discord.Intents.default()
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    client = discord.Client(
        intents=intents,
        connector=connector,
        proxy=settings.discord_proxy,
    )
    tree = app_commands.CommandTree(client)
    handler = DiscordCommandHandler(MockLLMProvider(), settings)

    @client.event
    async def on_ready() -> None:
        if settings.discord_guild_id:
            guild = discord.Object(id=int(settings.discord_guild_id))
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        else:
            await tree.sync()
        print(f"OscAgent Discord bot logged in as {client.user}.", flush=True)

    @tree.command(name="ask", description="Ask OscAgent a question.")
    @app_commands.describe(prompt="Question or task for OscAgent.")
    async def ask(interaction: discord.Interaction, prompt: str) -> None:
        await interaction.response.defer(thinking=True)
        response = await handler.handle_ask(prompt)
        await interaction.followup.send(response.content[:2000])

    @tree.command(name="status", description="Show OscAgent runtime status.")
    async def status(interaction: discord.Interaction) -> None:
        response = await handler.handle_status()
        await interaction.response.send_message(response.content[:2000], ephemeral=True)

    await client.start(settings.discord_bot_token)

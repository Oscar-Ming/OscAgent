import asyncio
import socket

from oscagent.config import Settings
from oscagent.discord_core import DiscordCommandHandler
from oscagent.llm import LLMRouter


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
    handler = DiscordCommandHandler(LLMRouter(settings), settings)

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

    @tree.command(name="memory", description="Inspect or delete OscAgent persistent memory.")
    @app_commands.describe(
        action="Memory action.",
        content="Search query or memory id depending on the action.",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="list", value="list"),
            app_commands.Choice(name="forget", value="forget"),
            app_commands.Choice(name="search", value="search"),
        ]
    )
    async def memory(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        content: str = "",
    ) -> None:
        if action.value == "list":
            memories = handler.list_memories(limit=10)
            response = _format_memories(memories)
            await interaction.response.send_message(response[:2000], ephemeral=True)
            return

        if action.value == "forget":
            try:
                memory_id = int(content.strip())
            except ValueError:
                await interaction.response.send_message(
                    "Please provide a numeric memory id.",
                    ephemeral=True,
                )
                return
            deleted = handler.forget_memory(memory_id)
            message = (
                f"Deleted memory {memory_id}."
                if deleted
                else f"Memory {memory_id} not found. You can also use `/ask 请忘记...`."
            )
            await interaction.response.send_message(message, ephemeral=True)
            return

        if action.value == "search":
            if not content.strip():
                await interaction.response.send_message("Search query is required.", ephemeral=True)
                return
            memories = handler.search_memories(content, limit=10)
            response = _format_memories(memories)
            await interaction.response.send_message(response[:2000], ephemeral=True)
            return

    await client.start(settings.discord_bot_token)


def _format_memories(memories: object) -> str:
    memory_records = list(memories)
    if not memory_records:
        return "No memories found."

    return "\n".join(f"{memory.id}. [{memory.scope}] {memory.content}" for memory in memory_records)

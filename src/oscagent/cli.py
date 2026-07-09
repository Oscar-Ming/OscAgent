from __future__ import annotations

import argparse
import asyncio
import sys

from oscagent import __version__
from oscagent.adapters.discord_bot import run_discord_bot
from oscagent.config import Settings
from oscagent.discord_core import DiscordCommandHandler
from oscagent.llm import LLMRouter
from oscagent.memory import MemoryRecord, MemoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oscagent",
        description="OscAgent command line tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subcommands = parser.add_subparsers(dest="command")

    doctor = subcommands.add_parser("doctor", help="Check local OscAgent configuration.")
    doctor.set_defaults(func=run_doctor)

    discord = subcommands.add_parser("discord", help="Run the Discord bot adapter.")
    discord.set_defaults(func=run_discord)

    ask = subcommands.add_parser("ask", help="Ask OscAgent from the local terminal.")
    ask.add_argument("prompt", nargs="+", help="Question or task for OscAgent.")
    ask.set_defaults(func=run_ask)

    memory = subcommands.add_parser("memory", help="Manage persistent OscAgent memory.")
    memory_subcommands = memory.add_subparsers(dest="memory_command")

    remember = memory_subcommands.add_parser("remember", help="Store a memory.")
    remember.add_argument("content", nargs="+", help="Memory content.")
    remember.add_argument("--scope", default="user", help="Memory scope.")
    remember.set_defaults(func=run_memory_remember)

    list_memory = memory_subcommands.add_parser("list", help="List recent memories.")
    list_memory.add_argument("--limit", type=int, default=10, help="Maximum memories to show.")
    list_memory.set_defaults(func=run_memory_list)

    forget = memory_subcommands.add_parser("forget", help="Delete a memory by id.")
    forget.add_argument("id", type=int, help="Memory id.")
    forget.set_defaults(func=run_memory_forget)

    search = memory_subcommands.add_parser("search", help="Search memories.")
    search.add_argument("query", nargs="+", help="Search query.")
    search.add_argument("--limit", type=int, default=5, help="Maximum memories to show.")
    search.set_defaults(func=run_memory_search)

    return parser


def build_memory_store() -> MemoryStore:
    return MemoryStore(Settings().db_path)


def format_memory(memory: MemoryRecord) -> str:
    return f"{memory.id}. [{memory.scope}] {memory.content} ({memory.source}, {memory.created_at})"


def run_memory_remember(args: argparse.Namespace) -> int:
    store = build_memory_store()
    memory = store.remember(" ".join(args.content), scope=args.scope, source="cli")
    print(f"Stored memory {memory.id}.")
    return 0


def run_memory_list(args: argparse.Namespace) -> int:
    store = build_memory_store()
    memories = store.list_memories(limit=args.limit)
    if not memories:
        print("No memories stored.")
        return 0

    for memory in memories:
        print(format_memory(memory))
    return 0


def run_memory_forget(args: argparse.Namespace) -> int:
    store = build_memory_store()
    deleted = store.forget(args.id)
    print(f"Deleted memory {args.id}." if deleted else f"Memory {args.id} not found.")
    return 0


def run_memory_search(args: argparse.Namespace) -> int:
    store = build_memory_store()
    memories = store.search(" ".join(args.query), limit=args.limit)
    if not memories:
        print("No matching memories.")
        return 0

    for memory in memories:
        print(format_memory(memory))
    return 0


def run_ask(args: argparse.Namespace) -> int:
    settings = Settings()
    handler = DiscordCommandHandler(LLMRouter(settings), settings)
    response = asyncio.run(handler.handle_ask(" ".join(args.prompt)))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(response.content)
    return 0


def run_discord(_: argparse.Namespace) -> int:
    run_discord_bot()
    return 0


def run_doctor(_: argparse.Namespace) -> int:
    settings = Settings()
    print("OscAgent doctor")
    print(f"- environment: {settings.env}")
    print(f"- default model: {settings.model}")
    print(f"- database path: {settings.db_path}")
    print(f"- discord token configured: {settings.discord_bot_token is not None}")
    print(f"- discord proxy configured: {settings.discord_proxy is not None}")
    print(f"- OpenAI key configured: {settings.openai_api_key is not None}")
    print(f"- DeepSeek key configured: {settings.deepseek_api_key is not None}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

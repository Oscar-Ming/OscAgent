from __future__ import annotations

import argparse
import asyncio
import sys

from oscagent import __version__
from oscagent.adapters.discord_bot import run_discord_bot
from oscagent.config import Settings
from oscagent.discord_core import DiscordCommandHandler
from oscagent.llm import LLMRouter


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

    return parser


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

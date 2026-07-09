# OscAgent

OscAgent is a lightweight Discord-first AI agent runtime for research and coding workflows.

The project goal is to build a small but complete personal agent system that can:

- talk with users through Discord;
- route requests to OpenAI-compatible providers such as OpenAI and DeepSeek;
- execute safe local tools for repository analysis and research tasks;
- store persistent project and user memory;
- expose traceable task logs for debugging and demonstration;
- run on both Windows and macOS.

## Why This Project Exists

OscAgent is designed as a graduate-application portfolio project. It focuses on practical agent architecture rather than a generic chatbot: planning, tool execution, memory, permissions, and cross-platform engineering.

## Initial Architecture

```text
Discord
  -> Discord Adapter
  -> Agent Core
  -> LLM Provider Router
  -> Tool Registry
  -> Memory Store / Task Logs
  -> Local Workspace + External APIs
```

## Planned Modules

| Module | Responsibility |
| --- | --- |
| Discord Adapter | Receive Discord commands/messages and send agent responses. |
| LLM Provider | Provide a unified interface for OpenAI, DeepSeek, and future OpenAI-compatible APIs. |
| Agent Core | Plan tasks, choose tools, observe results, and produce final answers. |
| Tool Registry | Register tools, validate inputs, execute actions, and format observations. |
| Memory System | Store user preferences, project context, and task summaries. |
| Permission Guard | Require confirmation for risky file, shell, or Git operations. |
| Task Logger | Record plans, tool calls, results, and errors for review. |

## Development Setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m oscagent doctor
```

Copy `.env.example` to `.env` and fill in API keys when you are ready to connect Discord and model providers.

You can test the local LLM path without Discord:

```bash
python -m oscagent ask "hello from OscAgent"
```

## Discord MVP

Phase 1 adds a Discord adapter with two slash commands:

| Command | Purpose |
| --- | --- |
| `/ask` | Send a question to OscAgent. The current implementation uses a mock LLM provider. |
| `/status` | Show runtime configuration status. |

Install Discord support:

```bash
python -m pip install -e ".[dev,discord]"
```

Create a `.env` file:

```bash
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_test_server_id
DISCORD_PROXY=http://127.0.0.1:7897
OSCAGENT_MODEL=mock:local
```

Run the bot:

```bash
python -m oscagent discord
```

`DISCORD_GUILD_ID` is optional, but setting it during development makes slash command syncing faster for one test server.
`DISCORD_PROXY` is optional. Set it only if Python cannot connect to Discord directly and your system uses a local proxy.

## LLM Providers

`OSCAGENT_MODEL` uses this format:

```text
provider:model
```

Supported providers:

| Provider | Example | Required environment variables |
| --- | --- | --- |
| Mock | `mock:local` | None |
| OpenAI | `openai:gpt-4.1-mini` | `OPENAI_API_KEY` |
| DeepSeek | `deepseek:deepseek-chat` | `DEEPSEEK_API_KEY` |

Example OpenAI config:

```env
OSCAGENT_MODEL=openai:gpt-4.1-mini
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
```

Example DeepSeek config:

```env
OSCAGENT_MODEL=deepseek:deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

If your network requires a proxy for model API calls:

```env
LLM_PROXY=http://127.0.0.1:7897
```

## Read-only Agent Tools

Phase 3 adds a controlled repository analysis workflow. If a prompt asks to analyze
the repo or project structure, OscAgent runs a small read-only tool plan before
asking the model to summarize the result.

Initial tools:

| Tool | Purpose |
| --- | --- |
| `list_files` | List workspace files with ignored build/cache/log folders filtered out. |
| `read_file` | Read selected text files inside the workspace. |
| `search_text` | Search workspace text files for literal matches. |
| `git_status` | Show branch and working tree state. |

Example:

```bash
python -m oscagent ask "analyze repo"
```

Discord:

```text
/ask analyze repo
```

## Roadmap

See [ROADMAP.md](ROADMAP.md).

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

## Roadmap

See [ROADMAP.md](ROADMAP.md).

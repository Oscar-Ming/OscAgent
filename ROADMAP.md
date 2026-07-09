# OscAgent Roadmap

## Phase 0: Project Foundation

- Create Python package structure.
- Add cross-platform configuration loading.
- Add `.env.example` and `.gitignore`.
- Add basic CLI and tests.
- Prepare GitHub-ready README.

## Phase 1: Discord MVP

- Create Discord bot adapter.
- Support `/ask` for simple model-backed conversation.
- Add local development instructions for Discord bot tokens.
- Add tests around message normalization.

## Phase 2: LLM Provider Layer

- Add a provider-agnostic chat interface.
- Support OpenAI.
- Support DeepSeek through an OpenAI-compatible endpoint.
- Add model selection through config and Discord commands.

## Phase 3: Agent Core and Tools

- Implement a small planning/execution loop.
- Add file tools: list files, read file, search text.
- Add safe command execution with permission checks.
- Add task trace logs.

## Phase 4: Persistent Memory

- Add SQLite storage.
- Store conversation summaries and user preferences.
- Add memory retrieval before agent execution.
- Add commands to inspect and delete memory.

## Phase 5: Portfolio Polish

- Add architecture diagram.
- Add demo scripts and screenshots.
- Add case studies for repository analysis and research assistance.
- Tag a `v0.1.0` release.

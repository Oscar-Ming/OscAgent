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
- Support `/status` for runtime checks.
- Add local development instructions for Discord bot tokens.
- Add tests around Discord command handling.

## Phase 2: LLM Provider Layer

- Add a provider-agnostic chat interface.
- Support OpenAI.
- Support DeepSeek through an OpenAI-compatible endpoint.
- Add model selection through config.
- Add local terminal testing with `oscagent ask`.

## Phase 3: Agent Core and Tools

- Implement a controlled repository analysis workflow.
- Add read-only tools: list files, read file, search text, git status.
- Add workspace path sandboxing for file tools.
- Add task trace logs.
- Route repo-analysis prompts from Discord to the agent workflow.

## Phase 4: Persistent Memory

- Add SQLite storage.
- Store user/project memories through CLI and Discord.
- Add memory retrieval before ordinary `/ask` responses.
- Add commands to inspect, search, and delete memory.
- Keep memory local through `OSCAGENT_DB_PATH`.

## Phase 4.1: Memory UX Hardening

- Route natural-language remember, forget, list, and clear-all requests through `/ask`.
- Keep `/memory` focused on inspection and manual cleanup.
- Require confirmation before clearing all memories.
- Harden Chinese/English memory matching tests.

## Phase 5: Permission Guard and File Operations

- Add permission levels for read-only, workspace write, file move, and dangerous actions.
- Add confirmation flow for write and move operations.
- Add safe file tools such as create directory, write file, copy file, and move file.
- Keep all file operations inside approved workspace roots.
- Store pending actions in SQLite and support confirm/cancel.
- Add natural-language variants and pending action inspection.

## Phase 6: Planner Agent Loop

- Add a model-driven planner that turns natural-language workspace requests into
  multiple registered tool operations.
- Use one provider-independent JSON plan protocol for DeepSeek, OpenAI, and future
  model providers.
- Validate tool names, argument schemas, workspace paths, and operation counts.
- Route planned write/move actions into pending confirmation instead of executing
  immediately.
- Record a visible plan trace and retain deterministic planners as reliable fast paths.

## Phase 7: Safe Shell and Git Tools

- Add allowlisted shell commands such as tests, lint, and Git inspection.
- Add Git workflow helpers with confirmation for commit and push.

## Phase 8: Browser Automation

- Add Playwright-backed browser open, search, and page summarization tools.
- Keep browser automation traceable and bounded.

## Phase 9: Portfolio Polish

- Add architecture diagram.
- Add demo scripts and screenshots.
- Add case studies for repository analysis and research assistance.
- Tag a `v0.1.0` release.

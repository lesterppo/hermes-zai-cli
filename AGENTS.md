# zai CLI — for AI agents

Agent-native, token-efficient CLI for chat.z.ai (GLM). HTTP-first except `chat`.

Agent conventions:
- Output = pointer JSON on stdout, payloads to `~/.zai-cli/out/<cmd>-<ts>.json`.
- Always pass `--json` and read the file path in `f` for full data; the inline keys
  (`models`, `chats`, `answer`, ...) are compact summaries.
- Errors are `{"ok": false, "err": ..., "msg": ...}`.
- `zai chat "<prompt>"` is the only command that launches a browser (captcha-gated by the
  site). For pure-metadata lookups use `models` / `whoami` / `chats` / `scene`.

Typical agent flows:
- Pick a model: `zai --json models`
- Check auth/role: `zai --json whoami`
- List history: `zai --json chats --limit 20`
- Ask GLM: `zai --json chat "question"` → `f` points at the answer JSON; `answer` inline.
- Compute a signature: `zai sig "<text>"` → `signature` inline.

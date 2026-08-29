# zai — AI-agent-native CLI for Z.ai (GLM-5.3-Flash / GLM-5.3 family)

A token-efficient, HTTP-first CLI for [chat.z.ai](https://chat.z.ai) — Zhipu's GLM
chatbot (GLM-5.3-Flash / GLM-5.3 / GLM-5.2 / GLM-4.7 / reasoning models). Talks to the
site's own API; no official API key required.

- **HTTP-first.** The full read/metadata surface (`models`, `whoami`, `chats`, `folders`,
  `tags`, `pinned`, `settings`, `scene`) and the site's `X-Signature` anti-tamper protocol are
  reimplemented over pure HTTP — no browser, sub-second, token-efficient pointer-JSON output.
- **`chat` is browser-backed by necessity.** chat.z.ai gates *every* completion behind an
  interactive slider captcha + risk engine. The captcha token is bound to the solving
  browser's fingerprint and cannot be replayed over pure HTTP (verified: a replay always
  returns `FRONTEND_CAPTCHA_REQUIRED`). So `zai chat` drives the logged-in browser, submits
  the message, and returns the assistant reply after you drag the slider. One browser
  touchpoint; everything else is HTTP.

## Install

```bash
git clone https://github.com/lesterppo/hermes-zai-cli.git && cd hermes-zai-cli
./install.sh            # symlinks zai -> ~/.local/bin/zai, installs curl_cffi + playwright
zai login               # opens a headed browser; sign in (Google/GitHub/email); session persists
```

`curl_cffi` is required for the HTTP layer (chat.z.ai sits behind Alibaba WAF that blocks
plain `urllib`/`requests` TLS fingerprints). `playwright` is only needed for `zai chat`.

## Usage

```bash
zai --json models              # all GLM models (GLM-5.3-Flash etc.)
zai --json whoami              # auth profile / role
zai --json chats --limit 20    # recent chat history
zai --json folders              # folders
zai --json tags                # chat tags
zai --json pinned              # pinned chats
zai --json settings            # user settings
zai --json scene --model x-preview-l   # scene config / suggestion prompts
zai sig '<prompt>'             # compute the X-Signature for a payload (debug/tools)

zai chat "What is fibonacci(10)?"   # browser-backed; drag the slider when prompted
```

Output contract — pointer JSON on stdout, full data to disk:

```json
{"ok": true, "f": "/home/$USER/.zai-cli/out/models-1737000000.json", "s": 15, "models": ["x-preview-l", "..."]}
```

Errors are JSON (`{"ok": false, "err": "...", "msg": "..."}`), never tracebacks.

## Auth

The Bearer token is read from the persistent browser profile `~/.zai-cli/login-profile`
(`localStorage['token']`), or via `ZAI_TOKEN`. `zai login` establishes the session.

## Reverse-engineered protocol (for tool builders)

- **Endpoints** under `https://chat.z.ai/api`: `/models` (OpenAI-format), `/v1/auths/`,
  `/v1/chats/` (list, `?page=&type=`), `/v1/chats/all/tags`, `/v1/chats/pinned`,
  `/v1/folders/`, `/v1/users/user/settings`, `/v1/scene-cfg/?model=`.
- **Completion** (captcha-gated): `POST /api/v2/chat/completions?<env>` with
  `Authorization: Bearer <token>`, `X-FE-Version: prod-fe-1.1.92`, `X-Signature`, body =
  `{stream, model, messages, signature_prompt, features, ...}`. SSE events
  `data: {"type":"chat:completion","data":{"delta_content":"...","phase":"thinking"}}`.
- **X-Signature** = `HMAC-SHA256( key=HMAC-SHA256("key-@@@@)))()((9))-xxxx&&&%%%%%", msg=floor(ts/300000) ),
  msg = "requestId:...,timestamp:...,user_id:..." + "|" + base64(token) + "|" + ts )` hex.
- **Models**: `x-preview-l` (GLM-5.3-Flash), `glm-5.3`, `glm-5.2`, `GLM-5-Turbo`, `GLM-5v-Turbo`,
  `glm-4.7`, `glm-4.6v`, `GLM-4.5`, `GLM-4.5-Air`, `deep-research` (Z1-Rumination), `zero` (Z1-32B), …
- A pure-HTTP completion always returns `FRONTEND_CAPTCHA_REQUIRED` — the slider is authoritative.

## License

MIT

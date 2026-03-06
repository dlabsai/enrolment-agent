For all things python use `uv` (e.g., use `uv run` instead of `python` or `python3`)

In `backend/` and `frontend/`:
- lint, type-check, etc., with `check.sh`
- format (when asked) with `format.sh` 

You can read multiple files at once via `uvx files-to-prompt` command, but the output will be capped at 50KB

Read `frontend/AGENTS.md` and `backend/AGENTS.md`

Specs:
- Requirements-only specs live in `docs/specs/` (see `docs/specs/README.md`).
- Keep specs in sync with implementation changes.

Check `.venv` and `node_modules` for external API type definitions instead of guessing

Always ask before removing functionality or code that appears to be intentional

NEVER commit unless user asks

Commands: prefer full output (avoid truncating logs with `tail`, etc.)

Style:
- Keep answers short and concise
- No emojis in commits or code
- No fluff or cheerful filler text
- Technical prose only, be kind but direct (e.g., "Thanks @user" not "Thanks so much @user!")

Read `docs/README.md` for additional docs

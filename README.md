# community

The Picture of Two Discord server, as code. Shared by all our games.

- `discord/setup.py` — brings the server to its structure (channels, roles, permissions, forum tags). Idempotent, never deletes.
  Run locally; reads the bot token from `C:\Users\efvhd\.secrets\discord.env`.
- `bot/bug-issues.mjs` — every 10 minutes (`.github/workflows/bug-issues.yml`) turns new `#bug-reports` posts into GitHub
  issues in the game's repo, by the post's game tag, and marks the post `Tracked`. `--dry` prints instead of writing.
- `discord/posts/*.md` + `discord/post.py` — the server's texts. Preview by default; `--send` posts or edits the same
  message, only after the owner's yes.
- `config.json` — game tag → repo, type tag → label. A new game is one line here plus its tag in `discord/setup.py`.

Secrets (repo settings): `DISCORD_TOKEN` (bot), `ISSUES_TOKEN` (fine-grained GitHub token, Issues: read and write on every game
repo). The repo is public, so are Actions logs: the bot logs counts only.

Limit: GitHub turns off scheduled workflows in a public repo after 60 days without commits; re-enable in the Actions tab.

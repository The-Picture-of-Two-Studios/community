"""Post or update one approved text from discord/posts/ as the bot.

  python discord/post.py rules rules                         -> preview only
  python discord/post.py start-here start-here GAME_URL=https://... --send

Every post goes out only with the owner's yes, hence the explicit --send. A second --send edits the same message
(ids kept in posts/ids.json), so fixing a text never makes a duplicate. Refuses while a {PLACEHOLDER} is left.
"""
import json, pathlib, re, sys, urllib.request, urllib.error

ENV = r"C:\Users\efvhd\.secrets\discord.env"
HERE = pathlib.Path(__file__).parent
CFG = json.loads((HERE.parent / "config.json").read_text(encoding="utf-8"))
IDS = HERE / "posts" / "ids.json"

args = [a for a in sys.argv[1:] if a != "--send"]
send = "--send" in sys.argv
if len(args) < 2:
    sys.exit(__doc__)
name, channel, *pairs = args
text = (HERE / "posts" / f"{name}.md").read_text(encoding="utf-8")
for k, v in (p.split("=", 1) for p in pairs):
    text = text.replace("{" + k + "}", v)
left = re.findall(r"\{[A-Z_0-9]+\}", text)
if len(text) > 2000:
    sys.exit(f"{len(text)} characters, Discord allows 2000")
print(text)
if left:
    sys.exit(f"\nnot sent: fill {', '.join(sorted(set(left)))}")
if not send:
    sys.exit("\npreview only: add --send to post")

env = dict(l.strip().split("=", 1) for l in open(ENV, encoding="utf-8") if "=" in l)
TOKEN = env["DISCORD_TOKEN"].strip().strip('"')


def call(method, path, body=None):
    req = urllib.request.Request("https://discord.com/api/v10" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bot " + TOKEN, "Content-Type": "application/json",
                                          "User-Agent": "DiscordBot (tpo2-community, 1)"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code} {e.read().decode()}")


channels = call("GET", f"/guilds/{CFG['guild']}/channels")
chan = next((c for c in channels if c["name"] == channel), None)
if not chan:
    sys.exit(f"no channel #{channel}")
for c in channels:  # "#bug-reports" in a text becomes a clickable channel link
    if c["type"] in (0, 5, 15):
        text = re.sub(r"#" + re.escape(c["name"]) + r"(?![\w-])", f"<#{c['id']}>", text)
ids = json.loads(IDS.read_text(encoding="utf-8")) if IDS.exists() else {}
key = f"{channel}/{name}"
body = {"content": text, "allowed_mentions": {"parse": []}}
if key in ids:
    msg = call("PATCH", f"/channels/{chan['id']}/messages/{ids[key]}", body)
else:
    msg = call("POST", f"/channels/{chan['id']}/messages", body)
    ids[key] = msg["id"]
    IDS.write_text(json.dumps(ids, indent=1) + "\n", encoding="utf-8")
print(f"\nposted: https://discord.com/channels/{CFG['guild']}/{chan['id']}/{msg['id']}")

"""Bring the Discord server to the structure below. Idempotent: finds by name/id, never deletes."""
import json, sys, time, urllib.request, urllib.error

ENV = r"C:\Users\efvhd\.secrets\discord.env"
GUILD = "1545766637603659818"
API = "https://discord.com/api/v10"

env = dict(l.strip().split("=", 1) for l in open(ENV, encoding="utf-8") if "=" in l)
TOKEN = env["DISCORD_TOKEN"].strip().strip('"')


def call(method, path, body=None):
    for _ in range(5):
        req = urllib.request.Request(API + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bot " + TOKEN, "Content-Type": "application/json",
                                              "User-Agent": "DiscordBot (tpot-setup, 1)",
                                              "X-Audit-Log-Reason": "server setup"})
        try:
            with urllib.request.urlopen(req) as r:
                t = r.read()
                return json.loads(t) if t else None
        except urllib.error.HTTPError as e:
            t = e.read().decode()
            if e.code == 429:
                time.sleep(json.loads(t).get("retry_after", 1) + 0.2)
                continue
            sys.exit(f"{method} {path} -> {e.code} {t}")


VIEW, SEND, CONNECT = 1 << 10, 1 << 11, 1 << 20
THREADS = (1 << 35) | (1 << 36)  # create public/private threads
TEXT, VOICE, CAT, NEWS, FORUM = 0, 2, 4, 5, 15

roles = call("GET", f"/guilds/{GUILD}/roles")
role = {r["name"]: r["id"] for r in roles}
EVERYONE = GUILD
if "Tester" not in role:
    role["Tester"] = call("POST", f"/guilds/{GUILD}/roles", {"name": "Tester", "color": 0x3BA55C, "hoist": True,
                                                              "mentionable": True})["id"]
TEAM, TESTER = role["Team"], role["Tester"]


def ow(id_, allow=0, deny=0):
    return {"id": id_, "type": 0, "allow": str(allow), "deny": str(deny)}


PERMS = {
    "public": [],
    "readonly": [ow(EVERYONE, deny=SEND | THREADS), ow(TEAM, allow=SEND | THREADS)],
    "testers": [ow(EVERYONE, deny=VIEW), ow(TESTER, allow=VIEW), ow(TEAM, allow=VIEW)],
    "team": [ow(EVERYONE, deny=VIEW), ow(TEAM, allow=VIEW)],
}

BUG_TAGS = ["Isekai Architect", "Gameplay", "Visual", "Server", "Crash", "Tracked"]
MODERATED = {"Tracked"}  # only the team and the bot can set it

# category name (old names it may carry) -> perms, channels: (name, type, old names, extra)
LAYOUT = [
    ("INFO", [], "readonly", [
        ("rules", TEXT, [], {"topic": "Server rules. Read before posting."}),
        ("announcements", TEXT, [], {"topic": "News and releases."}),
        ("dev-diary", TEXT, [], {"topic": "How the games are made."}),
        ("start-here", TEXT, [], {"topic": "What we make and how to play."}),
    ]),
    ("COMMUNITY", ["Голосовые каналы"], "public", [
        ("general", TEXT, [], {}),
        ("bug-reports", FORUM, [], {"topic": "One bug per post. Pick a game tag and a type tag.",
                                     "tags": BUG_TAGS, "flags": 16}),
        ("ideas", FORUM, [], {"topic": "Suggestions. One idea per post.", "tags": ["Isekai Architect"]}),
        ("Main", VOICE, [], {}),
    ]),
    ("PLAYTEST", [], "testers", [
        ("playtest-brief", TEXT, [], {"topic": "What to watch in the current test, what to compare against."}),
        ("playtest-feedback", FORUM, [], {"topic": "One post per test session."}),
    ]),
    ("TEAM", ["Текстовые каналы"], "team", [
        ("art", TEXT, [], {}), ("lore", TEXT, [], {}), ("mechanics", TEXT, [], {}),
        ("discussion", FORUM, [], {}), ("Discussion", VOICE, [], {}),
        ("bot-log", TEXT, [], {"topic": "Automation log and Discord moderator updates."}),
    ]),
]

g = call("GET", f"/guilds/{GUILD}")
call("PATCH", f"/guilds/{GUILD}", {"verification_level": 2, "explicit_content_filter": 2})

chans = call("GET", f"/guilds/{GUILD}/channels")


def find(name, type_, olds=()):
    for c in chans:
        if c["type"] == type_ and c["name"] in (name, *olds):
            return c
    return None


ids = {}
for pos, (cname, olds, perm, children) in enumerate(LAYOUT):
    over = PERMS[perm]
    cat = find(cname, CAT, olds)
    body = {"name": cname, "position": pos, "permission_overwrites": over}
    cat = call("PATCH", f"/channels/{cat['id']}", body) if cat else call("POST", f"/guilds/{GUILD}/channels",
                                                                          {**body, "type": CAT})
    for cpos, (name, type_, olds2, extra) in enumerate(children):
        c = find(name, type_, olds2) or (find(name, NEWS) if type_ == TEXT else None)
        body = {"name": name, "parent_id": cat["id"], "position": cpos, "permission_overwrites": over}
        if "topic" in extra:
            body["topic"] = extra["topic"]
        if "flags" in extra:
            body["flags"] = extra["flags"]
        if "tags" in extra:
            have = {t["name"]: t for t in (c or {}).get("available_tags", [])}
            body["available_tags"] = [have.get(t, {"name": t, "moderated": t in MODERATED}) for t in extra["tags"]] + \
                                     [t for n, t in have.items() if n not in extra["tags"]]
        c = call("PATCH", f"/channels/{c['id']}", body) if c else call("POST", f"/guilds/{GUILD}/channels",
                                                                        {**body, "type": type_})
        ids[name] = c["id"]

# Community: unlocks announcement channels, welcome screen, onboarding.
if "COMMUNITY" not in g["features"]:
    call("PATCH", f"/guilds/{GUILD}", {"features": g["features"] + ["COMMUNITY"], "rules_channel_id": ids["rules"],
                                       "public_updates_channel_id": ids["bot-log"], "preferred_locale": "en-US"})
for name in ("announcements", "dev-diary"):
    if call("GET", f"/channels/{ids[name]}")["type"] == TEXT:
        call("PATCH", f"/channels/{ids[name]}", {"type": NEWS})

# AutoMod: spam + mass mentions.
rules = {r["name"] for r in call("GET", f"/guilds/{GUILD}/auto-moderation/rules")}
block = [{"type": 1, "metadata": {}}]
if "Spam" not in rules:
    call("POST", f"/guilds/{GUILD}/auto-moderation/rules",
         {"name": "Spam", "event_type": 1, "trigger_type": 3, "actions": block, "enabled": True})
if "Mention spam" not in rules:
    call("POST", f"/guilds/{GUILD}/auto-moderation/rules",
         {"name": "Mention spam", "event_type": 1, "trigger_type": 5,
          "trigger_metadata": {"mention_total_limit": 5, "mention_raid_protection_enabled": True},
          "actions": block + [{"type": 2, "metadata": {"channel_id": ids["bot-log"]}}], "enabled": True})
print("ok")

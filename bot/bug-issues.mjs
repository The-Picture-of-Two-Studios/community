// #bug-reports forum -> one GitHub issue per post, in the repo of the post's game tag.
// A handled post gets the moderated "Tracked" tag; the issue body carries the thread id, so a crash
// between "issue created" and "tag set" does not make a duplicate on the next run.
// Logs only counts: the repo is public, so are its Actions logs.
// Env: DISCORD_TOKEN, ISSUES_TOKEN (GitHub, Issues: write on every game repo). --dry prints instead of writing.
import { readFileSync } from 'node:fs';

const cfg = JSON.parse(readFileSync(new URL('../config.json', import.meta.url), 'utf8'));
const DRY = process.argv.includes('--dry');
const { DISCORD_TOKEN, ISSUES_TOKEN } = process.env;
if (!DISCORD_TOKEN || (!DRY && !ISSUES_TOKEN)) throw new Error('DISCORD_TOKEN and ISSUES_TOKEN are required');

async function discord(method, path, body) {
  for (;;) {
    const r = await fetch('https://discord.com/api/v10' + path, {
      method,
      headers: { Authorization: 'Bot ' + DISCORD_TOKEN, 'Content-Type': 'application/json' },
      body: body && JSON.stringify(body),
    });
    if (r.status === 429) {
      const wait = ((await r.json()).retry_after + 0.2) * 1000;
      await new Promise(res => setTimeout(res, wait));
      continue;
    }
    if (!r.ok) throw new Error(`discord ${method} ${path} -> ${r.status} ${await r.text()}`);
    return r.status === 204 ? null : r.json();
  }
}

async function github(method, path, body) {
  const r = await fetch('https://api.github.com' + path, {
    method,
    headers: { Authorization: 'Bearer ' + ISSUES_TOKEN, Accept: 'application/vnd.github+json', 'User-Agent': 'tpo2-community-bot' },
    body: body && JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`github ${method} ${path} -> ${r.status} ${await r.text()}`);
  return r.json();
}

const marker = id => `<!-- discord-thread:${id} -->`;

const channels = await discord('GET', `/guilds/${cfg.guild}/channels`);
const forum = channels.find(c => c.type === 15 && c.name === cfg.bugForum);
const tagName = Object.fromEntries(forum.available_tags.map(t => [t.id, t.name]));
const tracked = forum.available_tags.find(t => t.name === cfg.trackedTag);
if (!tracked) throw new Error(`forum has no "${cfg.trackedTag}" tag`);

const active = (await discord('GET', `/guilds/${cfg.guild}/threads/active`)).threads;
const archived = (await discord('GET', `/channels/${forum.id}/threads/archived/public?limit=50`)).threads;
const threads = [...active, ...archived].filter(t => t.parent_id === forum.id && !t.applied_tags.includes(tracked.id));

const known = new Map(); // repo -> Set of thread ids that already have an issue
async function alreadyFiled(repo, threadId) {
  if (DRY || !ISSUES_TOKEN) return false;
  if (!known.has(repo)) {
    const issues = await github('GET', `/repos/${repo}/issues?labels=from-discord&state=all&per_page=100`);
    known.set(repo, new Set(issues.flatMap(i => [...(i.body ?? '').matchAll(/discord-thread:(\d+)/g)].map(m => m[1]))));
  }
  return known.get(repo).has(threadId);
}

let filed = 0, skipped = 0;
for (const t of threads) {
  const tags = t.applied_tags.map(id => tagName[id]);
  const game = tags.find(n => cfg.games[n]);
  if (!game) { skipped++; continue; }
  const repo = cfg.games[game];
  const labels = ['bug', 'from-discord', ...tags.map(n => cfg.types[n]).filter(Boolean)];
  const starter = await discord('GET', `/channels/${t.id}/messages/${t.id}`).catch(() => null);
  const link = `https://discord.com/channels/${cfg.guild}/${t.id}`;
  const files = (starter?.attachments ?? []).map(a => `- ${a.url}`).join('\n');
  const body = [
    `Reported on Discord by **${starter?.author?.username ?? 'unknown'}**: ${link}`,
    '',
    starter?.content || '_(no text)_',
    files && `\n**Attachments** (Discord links expire after about a day):\n${files}`,
    '',
    marker(t.id),
  ].filter(x => x !== '').join('\n');

  if (DRY) { console.log({ repo, title: t.name, labels, body }); continue; }
  if (!(await alreadyFiled(repo, t.id))) {
    await github('POST', `/repos/${repo}/issues`, { title: t.name, body, labels });
  }
  await discord('PATCH', `/channels/${t.id}`, { applied_tags: [tracked.id, ...t.applied_tags].slice(0, 5) });
  filed++;
}
console.log(`bug-issues: ${threads.length} untracked, ${filed} filed, ${skipped} without a game tag${DRY ? ' (dry run)' : ''}`);

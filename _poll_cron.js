const fs = require('fs');
const path = require('path');

const JOBS = path.join(process.env.APPDATA, 'knight-trader', 'hermes', 'cron', 'jobs.json');
const SESSIONS = path.join(process.env.APPDATA, 'knight-trader', 'hermes', 'sessions');

function dumpKind() {
  if (!fs.existsSync(SESSIONS)) return { file: null, kind: 'none' };
  const files = fs.readdirSync(SESSIONS)
    .filter((name) => name.startsWith('request_dump_cron_') && name.endsWith('.json'))
    .map((name) => ({ name, mtime: fs.statSync(path.join(SESSIONS, name)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);
  if (!files.length) return { file: null, kind: 'none' };
  const raw = fs.readFileSync(path.join(SESSIONS, files[0].name), 'utf8');
  const auth = raw.match(/"Authorization":\s*"([^"]+)"/);
  const value = auth ? auth[1] : '';
  let kind = 'missing';
  if (/no-key/i.test(value)) kind = 'no-key-required';
  else if (/sk-nous/i.test(value)) kind = 'sk-nous';
  else if (/Bearer /i.test(value)) kind = 'other-bearer';
  return { file: files[0].name, kind };
}

async function main() {
  const start = JSON.parse(fs.readFileSync(JOBS, 'utf8')).jobs[0];
  console.log(JSON.stringify({
    start_last_run: start.last_run_at,
    start_next_run: start.next_run_at,
    start_status: start.last_status,
  }));
  const deadline = Date.now() + 150000;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 5000));
    const job = JSON.parse(fs.readFileSync(JOBS, 'utf8')).jobs[0];
    const dump = dumpKind();
    const ran = job.last_run_at !== start.last_run_at;
    console.log(JSON.stringify({
      state: job.state,
      last_status: job.last_status,
      ran,
      dump: dump.kind,
      next: job.next_run_at,
    }));
    if (ran && job.state !== 'running') {
      console.log('RESULT', JSON.stringify({
        last_status: job.last_status,
        last_error: job.last_error ? String(job.last_error).slice(0, 200) : null,
        auth: dump.kind,
      }));
      return;
    }
  }
  console.log('RESULT timeout', JSON.stringify({ dump: dumpKind() }));
}

main();

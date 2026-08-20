const path = require('path');
const fs = require('fs');
const { BlohunterBridge } = require('./blohunter-bridge');

const tmp = path.join(__dirname, '_tmp_hermes_home');
const out = path.join(tmp, 'cron', 'output', 'job1');
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(tmp, 'cron', 'jobs.json'), JSON.stringify({
  jobs: [
    { id: 'job1', name: 'demo-job', last_status: 'ok', last_run_at: '2026-08-14T09:00:00.000Z', last_error: '' },
  ],
}, null, 2));
fs.writeFileSync(path.join(out, '2026-08-14_09-00-00.md'), `# Cron Job: demo-job (OK)\n\n**Run Time:** 2026-08-14 09:00:00\n\nPipe fixed. One trade placed and verified.\n`);

const bridge = new BlohunterBridge({ userDataPath: tmp, log: () => {} });
const entries = bridge.readHermesActivityEntries(10);
console.log(JSON.stringify(entries, null, 2));
console.log('count', entries.length);

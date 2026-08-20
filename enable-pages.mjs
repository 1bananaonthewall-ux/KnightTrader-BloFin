import https from 'node:https';

const token = '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';
const repo = 'mknight2690-sys/knighttrader-blo-site';
const body = JSON.stringify({ source: { branch: 'master', path: '/' } });

const options = {
  hostname: 'api.github.com',
  path: `/repos/${repo}/pages`,
  method: 'PATCH',
  headers: {
    'Authorization': `token ${token}`,
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'Content-Type': 'application/json',
    'User-Agent': 'kt-pages-setup',
    'Content-Length': Buffer.byteLength(body),
  },
};

const req = https.request(options, (res) => {
  let data = '';
  res.on('data', (chunk) => { data += chunk; });
  res.on('end', () => {
    console.log(`STATUS: ${res.statusCode}`);
    console.log(data);
    process.exit(res.statusCode === 200 || res.statusCode === 201 ? 0 : 1);
  });
});

req.on('error', (err) => {
  console.error('REQUEST_ERROR', err.message);
  process.exit(1);
});

req.write(body);
req.end();

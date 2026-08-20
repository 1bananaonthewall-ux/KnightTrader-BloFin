const b = require('C:/Users/mknig/hermes-trader/KnightTrader/blohunter-bridge.js');
const root = b.resolveBlohunterConnectRoot();
console.log('root=' + (root || 'none'));
if (root) {
  const fs = require('fs');
  const path = require('path');
  console.log('has_dashboard=');
  console.log(fs.existsSync(path.join(root, 'src', 'dashboard', 'dashboard.html')));
  console.log('tree_top=');
  console.log(fs.readdirSync(root).join('\n'));
}

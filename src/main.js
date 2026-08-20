const { app, BrowserWindow } = require('electron');
const path = require('path');
const modulePath = require.resolve(path.join(__dirname, '..', 'KnightTrader', 'main.js'));
require(modulePath);

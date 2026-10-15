'use strict';
module.exports = {
  apps: [{
    name: 'dvbot',
    script: './src/main.js',
    cwd: __dirname,
    instances: 1,
    exec_mode: 'fork',
    autorestart: true,
    watch: false,
    restart_delay: 3000,
    kill_timeout: 45000,
    max_memory_restart: '512M',
    time: true
  }]
};


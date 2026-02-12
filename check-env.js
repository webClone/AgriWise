const dotenv = require('dotenv');
const fs = require('fs');

const envConfig = dotenv.parse(fs.readFileSync('.env'));

console.log('--- ENV CHECK ---');
for (const k in envConfig) {
    if (k.includes('SENTINEL') || k.includes('SECRET')) {
        console.log(`${k}: Length=${envConfig[k].length}, StartsWith=${envConfig[k].substring(0, 3)}...`);
    }
}
console.log('--- END CHECK ---');

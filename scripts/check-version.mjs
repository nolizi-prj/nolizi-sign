import fs from 'node:fs';

const version = fs.readFileSync(new URL('../VERSION', import.meta.url), 'utf8').trim();
if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error(`VERSION is not valid Semantic Versioning: ${version}`);
}

const jsonFiles = ['frontend/package.json', 'frontend/package-lock.json', 'service/package.json', 'service/package-lock.json'];
for (const file of jsonFiles) {
  const data = JSON.parse(fs.readFileSync(new URL(`../${file}`, import.meta.url), 'utf8'));
  if (data.version !== version) throw new Error(`${file} is ${data.version}; expected ${version}`);
  if (file.endsWith('package-lock.json') && data.packages?.['']?.version !== version) {
    throw new Error(`${file} root package is ${data.packages?.['']?.version}; expected ${version}`);
  }
}

const serviceSource = fs.readFileSync(new URL('../service/src/version.ts', import.meta.url), 'utf8');
if (!serviceSource.includes(`'${version}'`)) throw new Error('service/src/version.ts is not synchronized with VERSION');
console.log(`Version ${version} is synchronized.`);

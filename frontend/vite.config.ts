import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { cloudflare } from "@cloudflare/vite-plugin";

// https://vite.dev/config/
const productVersion = readFileSync(resolve(import.meta.dirname, '../VERSION'), 'utf8').trim()
let gitCommit = process.env.GITHUB_SHA?.slice(0, 12) || 'unknown'
try {
  gitCommit = execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { encoding: 'utf8' }).trim()
  if (execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim()) gitCommit += '-dirty'
} catch { /* build without .git */ }

export default defineConfig(({ mode }) => ({
  define: {
    __APP_VERSION__: JSON.stringify(productVersion),
    __APP_COMMIT__: JSON.stringify(gitCommit),
    __APP_BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    __APP_ENVIRONMENT__: JSON.stringify(process.env.PUMASI_DEPLOY_ENV || mode),
  },
  plugins: [vue(), cloudflare()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
}))

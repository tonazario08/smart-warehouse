import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { resolve, relative, join, sep } from 'node:path'
import { spawnSync } from 'node:child_process'

// Retain the original Node hook-host suite. Only its generated CJS input substitutes
// Vite's compile-time environment; actual Vite environment behavior has Vitest coverage.
const input = resolve('build/remediation-host-input')
const workspace = resolve('.')
if (JSON.parse(readFileSync('package.json', 'utf8')).name !== 'smart-warehouse-web') throw new Error('Run this preparation in the client workspace.')
for (const generated of [input, resolve('node_modules/.tmp/remediation-c'), resolve('node_modules/.tmp/remediation-suite')]) {
  if (!generated.startsWith(workspace + sep) || generated === workspace) throw new Error('Unsafe generated target.')
  if (existsSync(generated) && lstatSync(generated).isSymbolicLink()) throw new Error('Refusing a linked generated target.')
  rmSync(generated, { recursive: true, force: true })
}
mkdirSync(input, { recursive: true })
cpSync('src', join(input, 'src'), { recursive: true })
cpSync('tests', join(input, 'tests'), { recursive: true })
function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => entry.isDirectory()
    ? files(join(directory, entry.name)) : [join(directory, entry.name)])
}
for (const path of files(join(input, 'src')).filter(path => /\.[jt]sx?$/.test(path))) {
  const content = readFileSync(path, 'utf8')
  const replacement = content.replaceAll('import.meta.env.VITE_API_BASE_URL', '(globalThis as unknown as Record<string, string | undefined>).__figmaHostApiBase')
  if (replacement !== content) writeFileSync(path, replacement)
}
function run(args, options = {}) {
  const result = spawnSync(process.execPath, args, { stdio: 'inherit', ...options })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}
const compiler = resolve('node_modules/typescript/bin/tsc')
const flags = ['--ignoreConfig', '--module', 'commonjs', '--moduleResolution', 'bundler', '--target', 'es2022', '--jsx', 'react-jsx', '--esModuleInterop', '--skipLibCheck']
const source = files(join(input, 'src')).filter(path => /\.tsx?$/.test(path) && !path.includes('.test.') && !relative(join(input, 'src'), path).replaceAll('\\', '/').startsWith('test/'))
run([compiler, ...flags, '--outDir', 'node_modules/.tmp/remediation-c/src', '--rootDir', join(input, 'src'), ...source])
const tests = files(join(input, 'tests')).filter(path => path.endsWith('.test.js'))
run([compiler, ...flags, '--allowJs', '--checkJs', 'false', '--outDir', 'node_modules/.tmp/remediation-suite', '--rootDir', input, join(input, 'src/vite-env.d.ts'), ...tests])
const hosted = ['product-pagination.test.js', 'products-warehouses-remediation.test.js', 'ui-shell-remediation.test.js']
const helpers = readdirSync('node_modules/.tmp/remediation-suite/tests').filter(name => name.endsWith('.test.js') && !hosted.includes(name))
if (helpers.length !== tests.length - hosted.length) throw new Error('Compiled host helper inventory does not match the source tests.')
run(['--test', ...helpers.map(name => resolve('node_modules/.tmp/remediation-suite/tests/' + name)), ...hosted.map(name => resolve('tests/' + name))], {
  env: { ...process.env, PRODUCT_PAGINATION_SOURCE_ROOT: './node_modules/.tmp/remediation-c/src' },
})

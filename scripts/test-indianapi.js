const fs = require('fs');
const path = require('path');

const baseUrl = (process.env.INDIANAPI_BASE_URL || 'https://stock.indianapi.in').replace(/\/$/, '');
const apiKey = process.env.INDIANAPI_KEY || process.env.INDIAN_API_KEY;

function readSpec() {
  const candidates = [
    process.env.INDIANAPI_OPENAPI_PATH,
    path.join(process.cwd(), 'docs', 'api-1.json'),
    path.join(process.cwd(), 'api.json'),
    path.join(process.cwd(), 'backend', 'api.json'),
    path.join(process.cwd(), 'docs', 'api.json'),
  ].filter(Boolean);

  for (const file of candidates) {
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));
  }
  return null;
}

function enumValue(spec, endpoint, param) {
  const params = spec?.paths?.[endpoint]?.get?.parameters || [];
  const match = params.find((item) => item.name === param);
  const schema = resolveSchema(spec, match?.schema || {});
  return schema?.enum?.[0] || null;
}

function resolveSchema(spec, schema) {
  const refPrefix = '#/components/schemas/';
  if (!schema?.$ref?.startsWith(refPrefix)) return schema;
  const name = schema.$ref.slice(refPrefix.length);
  return spec?.components?.schemas?.[name] || schema;
}

async function call(endpoint, params = {}, allow403 = false) {
  if (!apiKey) {
    console.log(`${endpoint}: SKIP INDIANAPI_KEY is not configured`);
    return true;
  }

  const url = new URL(`${baseUrl}${endpoint}`);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value);
  }

  const started = Date.now();
  const res = await fetch(url, { headers: { 'x-api-key': apiKey } });
  const text = await res.text();
  const ok = res.ok || (allow403 && res.status === 403);
  console.log(`${endpoint}: ${ok ? 'OK' : 'FAIL'} status=${res.status} duration_ms=${Date.now() - started} body=${text.slice(0, 180)}`);
  return ok;
}

async function main() {
  const spec = readSpec();
  const stats = enumValue(spec, '/historical_stats', 'stats') || process.env.INDIANAPI_HISTORICAL_STATS || 'ratios';
  const period = enumValue(spec, '/historical_data', 'period');
  const filter = enumValue(spec, '/historical_data', 'filter');

  const tests = [
    ['/industry_search', { query: 'Tata' }],
    ['/stock', { name: 'Tata Steel' }],
    stats ? ['/historical_stats', { stock_name: 'Tata Steel', stats }] : null,
    ['/mutual_fund_search', { query: 'HDFC' }],
    ['/mutual_funds', {}],
    ['/corporate_actions', { stock_name: 'Tata Steel' }],
    ['/recent_announcements', { stock_name: 'Tata Steel' }],
    period && filter ? ['/historical_data', { stock_name: 'Tata Steel', period, filter }, true] : null,
  ];

  if (!enumValue(spec, '/historical_stats', 'stats')) {
    console.log(`/historical_stats: stats is a free string in docs/api-1.json; using ${stats}`);
  }
  if (!period || !filter) console.log('/historical_data: SKIP docs/api-1.json enum for period/filter not found');

  let passed = true;
  for (const test of tests) {
    if (!test) continue;
    const [endpoint, params, allow403] = test;
    passed = (await call(endpoint, params, allow403)) && passed;
  }
  process.exitCode = passed ? 0 : 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

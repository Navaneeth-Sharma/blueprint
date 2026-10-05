import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { handler } from '../server.js';

function listen() {
  return new Promise(resolve => {
    const server = http.createServer(handler).listen(0, () => resolve(server));
  });
}

test('shortens and redirects', async () => {
  const server = await listen();
  const base = `http://localhost:${server.address().port}`;
  const res = await fetch(`${base}/links`, { method: 'POST', body: JSON.stringify({ url: 'https://example.com/a' }) });
  assert.equal(res.status, 201);
  const { code } = await res.json();
  const hop = await fetch(`${base}/${code}`, { redirect: 'manual' });
  assert.equal(hop.status, 302);
  assert.equal(hop.headers.get('location'), 'https://example.com/a');
  server.close();
});

test('rejects a bad url', async () => {
  const server = await listen();
  const res = await fetch(`http://localhost:${server.address().port}/links`, { method: 'POST', body: '{"url":"nope"}' });
  assert.equal(res.status, 400);
  server.close();
});

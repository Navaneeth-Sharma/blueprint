// A tiny URL shortener: POST /links {"url"} -> 201 {"code"}; GET /<code> -> 302 to the url.
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const links = new Map();

export function handler(req, res) {
  if (req.method === 'POST' && req.url === '/links') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      let url;
      try {
        url = new URL(JSON.parse(body).url).href;
      } catch {
        res.writeHead(400, { 'content-type': 'text/plain' }).end('bad url');
        return;
      }
      const code = randomBytes(3).toString('hex');
      links.set(code, url);
      res.writeHead(201, { 'content-type': 'application/json' }).end(JSON.stringify({ code }));
    });
    return;
  }
  const code = req.url.slice(1);
  if (req.method === 'GET' && links.has(code)) {
    res.writeHead(302, { location: links.get(code) }).end();
    return;
  }
  res.writeHead(404, { 'content-type': 'text/plain' }).end('not found');
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 3000);
  http.createServer(handler).listen(port, () => console.log(`shorty on http://localhost:${port}`));
}

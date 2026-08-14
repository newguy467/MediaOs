import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve('/epg/public');
const port = Number(process.env.PORT || 3000);
const mime = { '.xml':'application/xml; charset=utf-8', '.gz':'application/gzip', '.json':'application/json; charset=utf-8' };

http.createServer((req, res) => {
  const raw = decodeURIComponent((req.url || '/').split('?')[0]);
  const rel = raw === '/' ? '/guide.xml' : raw;
  const target = path.resolve(root, '.' + rel);
  if (target !== root && !target.startsWith(root + path.sep)) {
    res.writeHead(400); return res.end('Bad path');
  }
  fs.stat(target, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404); return res.end('Not found'); }
    res.writeHead(200, { 'Content-Type': mime[path.extname(target)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
    fs.createReadStream(target).pipe(res);
  });
}).listen(port, '0.0.0.0', () => console.log(`[epg-server] listening on ${port}`));

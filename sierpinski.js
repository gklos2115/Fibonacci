// Trójkąt Sierpińskiego, n = 100, fioletowe odcienie -> sierpinski_n100.png
// Bez zależności: własny bufor RGB + kodowanie PNG przez wbudowany zlib.
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const N = 100;          // zadana liczba iteracji
const MIN_PX = 1;       // poniżej tego boku dalszy podział jest niewidoczny
const W = 4096, H = 3640;
const SIDE = 3960;
const TRI_H = SIDE * Math.sqrt(3) / 2;

// Efektywna głębokość: ile razy bok da się podzielić na pół, zanim spadnie < MIN_PX
const D_EFF = Math.min(N, Math.ceil(Math.log2(SIDE / MIN_PX)));

const buf = Buffer.alloc(W * H * 3);

function hslToRgb(h, s, l) {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const hp = h / 60;
  const x = c * (1 - Math.abs((hp % 2) - 1));
  let r = 0, g = 0, b = 0;
  if (hp < 1) [r, g, b] = [c, x, 0];
  else if (hp < 2) [r, g, b] = [x, c, 0];
  else if (hp < 3) [r, g, b] = [0, c, x];
  else if (hp < 4) [r, g, b] = [0, x, c];
  else if (hp < 5) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  const m = l - c / 2;
  return [r, g, b].map(v => Math.round((v + m) * 255));
}

// Kolor poziomu d: odcień 262°→292°, jasność 15%→85% liniowo z głębokością
function color(d) {
  const t = Math.min(d, D_EFF) / D_EFF;
  return hslToRgb(262 + 30 * t, 0.7, 0.15 + 0.70 * t);
}

function fillTriangle(a, b, c, rgb) {
  const minX = Math.max(0, Math.floor(Math.min(a[0], b[0], c[0])));
  const maxX = Math.min(W - 1, Math.ceil(Math.max(a[0], b[0], c[0])));
  const minY = Math.max(0, Math.floor(Math.min(a[1], b[1], c[1])));
  const maxY = Math.min(H - 1, Math.ceil(Math.max(a[1], b[1], c[1])));
  const area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  if (area === 0) return;
  for (let y = minY; y <= maxY; y++) {
    const py = y + 0.5;
    for (let x = minX; x <= maxX; x++) {
      const px = x + 0.5;
      const w0 = ((b[0] - px) * (c[1] - py) - (b[1] - py) * (c[0] - px)) / area;
      const w1 = ((c[0] - px) * (a[1] - py) - (c[1] - py) * (a[0] - px)) / area;
      const w2 = 1 - w0 - w1;
      if (w0 >= 0 && w1 >= 0 && w2 >= 0) {
        const i = (y * W + x) * 3;
        buf[i] = rgb[0]; buf[i + 1] = rgb[1]; buf[i + 2] = rgb[2];
      }
    }
  }
}

const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
let holes = 0;

function sierpinski(a, b, c, d, side) {
  if (d >= N || side < MIN_PX) return;
  const ab = mid(a, b), bc = mid(b, c), ca = mid(c, a);
  fillTriangle(ab, bc, ca, color(d + 1)); // wgłębienie poziomu d+1
  holes++;
  const half = side / 2;
  sierpinski(a, ab, ca, d + 1, half);
  sierpinski(ab, b, bc, d + 1, half);
  sierpinski(ca, bc, c, d + 1, half);
}

// Tło
const bg = hslToRgb(265, 0.35, 0.05);
for (let i = 0; i < buf.length; i += 3) { buf[i] = bg[0]; buf[i + 1] = bg[1]; buf[i + 2] = bg[2]; }

const x0 = (W - SIDE) / 2, y0 = (H - TRI_H) / 2;
const A = [x0 + SIDE / 2, y0], B = [x0, y0 + TRI_H], C = [x0 + SIDE, y0 + TRI_H];
fillTriangle(A, B, C, color(0));
sierpinski(A, B, C, 0, SIDE);

// --- PNG ---
const crcTable = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(b) {
  let c = 0xffffffff;
  for (let i = 0; i < b.length; i++) c = crcTable[(c ^ b[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}
const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(W, 0); ihdr.writeUInt32BE(H, 4);
ihdr[8] = 8; ihdr[9] = 2; // 8 bit, RGB
const raw = Buffer.alloc((W * 3 + 1) * H);
for (let y = 0; y < H; y++) buf.copy(raw, y * (W * 3 + 1) + 1, y * W * 3, (y + 1) * W * 3);
const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr),
  chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0)),
]);
const out = path.join(__dirname, 'sierpinski_n100.png');
fs.writeFileSync(out, png);
console.log(`n = ${N}, widoczne poziomy: ${D_EFF}, wgłębień: ${holes}, plik: ${out}`);

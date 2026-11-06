'use strict';
// 完整离线预演 mcu_flash_live.js flash 的全部校验，确定最小修正方案。
const path = require('path');
const crypto = require('crypto');
const fs = require('fs');
const DIR = path.resolve(__dirname, '..', 'neos75-fullscreen');
const manifest = JSON.parse(fs.readFileSync(DIR + '/firmware/fullscreen.patch.json', 'utf8'));
const pdir = DIR + '/firmware/profiles';
const profiles = [manifest, ...fs.readdirSync(pdir).filter(n => n.endsWith('.patch.json')).sort().map(n => JSON.parse(fs.readFileSync(pdir + '/' + n, 'utf8')))];
const sha = b => crypto.createHash('sha256').update(b).digest('hex');

const baseline = fs.readFileSync(path.join(__dirname, 'original.bin'));
const shipped = fs.readFileSync(path.join(__dirname, 'fullscreen.bin'));
const BASE = 0x8000, SEC = 8192, LEN = 491520, IMM = 487424;

// 每层的声明 changed_bytes 与实际净变化
const chain = ['reference-66679ff2', 'clean-8465dd63', 'widget-dce6dce7', 'widget-none-ec412e09'];
const out = Buffer.from(baseline);
for (const name of chain) {
  const layer = profiles.find(p => p.profile === name);
  const before = Buffer.from(out);
  for (const p of layer.patches) {
    const o = parseInt(p.offset, 16);
    Buffer.from(p.after, 'hex').copy(out, o);
  }
  let net = 0;
  for (let i = 0; i < baseline.length; i++) if (baseline[i] !== out[i]) net++;
  // 该层补丁相对上一层的实际改动
  let step = 0;
  for (let i = 0; i < baseline.length; i++) if (before[i] !== out[i]) step++;
  console.log(`${name}: declared=${layer.changed_bytes} stepVsPrev=${step} netVsBaseline=${net} sectors=${[...new Set(layer.patches.map(p => BASE + Math.floor(parseInt(p.offset, 16) / SEC) * SEC))].map(x => '0x' + x.toString(16)).join(',')}`);
}

// 实际差异扇区 vs allowedSectors
const sectors = [];
for (let o = 0; o < LEN; o += SEC) if (!out.subarray(o, o + SEC).equals(baseline.subarray(o, o + SEC))) sectors.push(o);
const known = [...new Set(chain.flatMap(n => profiles.find(p => p.profile === n).patches.map(p => BASE + Math.floor(parseInt(p.offset, 16) / SEC) * SEC)))].sort((a, b) => a - b);
console.log('diff sectors :', sectors.map(x => '0x' + x.toString(16)).join(','));
console.log('allowed sect :', known.map(x => '0x' + x.toString(16)).join(','));
console.log('sectors===allowed:', JSON.stringify(sectors) === JSON.stringify(known));

// 向量表 + 尾部 + 代码区 SHA + DFU 后缀完整性
console.log('vector table same:', out.subarray(0, 256).equals(baseline.subarray(0, 256)));
console.log('tail preserved   :', out.subarray(IMM).equals(baseline.subarray(IMM)));
console.log('code sha         :', sha(out.subarray(0, IMM)));
const m = profiles.find(p => p.profile === 'widget-none-ec412e09');
console.log('target code sha  :', m.target_code_sha256);
// shipped 的代码区/尾部与本机构造的 out 是否一致
console.log('shipped code==out:', shipped.subarray(0, LEN).subarray(0, IMM).equals(out.subarray(0, IMM)));
console.log('shipped tail==out:', shipped.subarray(0, LEN).subarray(IMM).equals(out.subarray(IMM)));
console.log('shipped suffix==suffix(out):', shipped.subarray(LEN).equals(buildSuffix(out)));
function buildSuffix(code) {
  const result = Buffer.concat([code, Buffer.from(m.dfu_suffix_prefix_hex, 'hex'), Buffer.alloc(4)]);
  let crc = 0xffffffff;
  for (const v of result.subarray(0, -4)) { crc ^= v; for (let k = 0; k < 8; k++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0); }
  result.writeUInt32LE(crc >>> 0, result.length - 4);
  return result.subarray(LEN);
}

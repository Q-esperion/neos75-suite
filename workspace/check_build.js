'use strict';
// 离线复现 exe 报错「目标代码或配置保留校验失败」：直接调用固件生成器比对。
const path = require('path');
const FW = require(path.join(__dirname, '..', 'neos75-fullscreen', 'tools', 'firmware_image.js'));
const fs = require('fs');

const baseline = fs.readFileSync(path.join(__dirname, 'original.bin'));
const shipped = fs.readFileSync(path.join(__dirname, 'fullscreen.bin'));

const id = FW.identify(baseline);
console.log('identify:', JSON.stringify(id));

const plan = FW.buildFirmware.plan(baseline);
console.log('planChain layers:', plan.layers.map(l => l.profile).join(' -> '));
console.log('blind:', plan.blind);

try {
  const out = FW.buildFirmware(baseline);
  console.log('buildFirmware: OK, len =', out.length);
  console.log('shipped.equals(built):', out.equals(shipped));
  if (!out.equals(shipped)) {
    for (let i = 0; i < Math.min(out.length, shipped.length); i++) {
      if (out[i] !== shipped[i]) { console.log('first diff at offset', i, '(0x' + i.toString(16) + ')'); break; }
    }
  }
} catch (e) {
  console.log('buildFirmware FAILED:', e.message);
  // 分解校验：手动打补丁看 changed 与 sha
  const layers = plan.layers;
  const m = layers[layers.length - 1];
  const out = Buffer.from(baseline);
  let changed = 0, mismatched = [];
  for (const layer of layers) for (const p of layer.patches) {
    const o = parseInt(p.offset, 16), before = Buffer.from(p.before, 'hex'), after = Buffer.from(p.after, 'hex');
    if (!out.subarray(o, o + before.length).equals(before)) mismatched.push(layer.profile + '@' + p.address);
    after.copy(out, o);
  }
  for (let i = 0; i < baseline.length; i++) if (baseline[i] !== out[i]) changed++;
  const expected = layers.reduce((n, l) => n + l.changed_bytes, 0);
  console.log('mismatched patches:', mismatched.length ? mismatched : '(none)');
  console.log('changed =', changed, ', expected =', expected);
  console.log('code sha =', FW.identify.length && require('crypto').createHash('sha256').update(out.subarray(0, m.immutable_payload_bytes)).digest('hex'));
  console.log('target_code_sha256 =', m.target_code_sha256, '(' + m.profile + ')');
}

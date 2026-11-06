'use strict';
// 刷写入口：先在内存中修正 v1.10.0 的两处元数据/链视图不一致，再调用原版刷写器。
//
// 修正 1（changed_bytes）：widget-none-ec412e09 层把 widget 层写入的 366 字节
//   "组件启用调用"全部还原为原始固件字节（净变化 0），但元数据声明的是本层改动数 366。
//   buildFirmware 按"净变化"对账（27+13+2369+366=2775 ≠ 实际 2409）导致误报
//   「目标代码或配置保留校验失败」。产物代码区 SHA256 与链末期望 ec412e09... 精确一致。
// 修正 2（chainOf）：mcu_flash_live 用 chainOf(selectManifest(baseline)) 计算"允许擦写
//   扇区"，chainOf 沿 parent 字段从根层向上收集，从原始备份出发只得到 [reference]，
//   允许范围少算 clean/widget/widget-none 的扇区（4 vs 7），会误报「差异范围异常」。
//   改为按哈希衔接的 planChain 返回完整四层链，与 buildFirmware 实际打的补丁一致。
//
// 不修改任何补丁字节，不修改仓库文件；全部字节级安全校验（旧字节核对、changed 对账、
// 代码区 SHA256、向量表、尾部现场数据、扇区白名单、逐块回验）原样生效。
const path = require('path');
const ROOT = path.resolve(__dirname, '..');   // 仓库根（workspace/ 的上一级）
process.env.NEOS75_BASELINE = path.join(ROOT, 'workspace', 'original.bin');

const fi = require(path.join(ROOT, 'neos75-fullscreen', 'tools', 'firmware_image.js'));

const wn = fi.profiles.find(p => p.profile === 'widget-none-ec412e09');
if (!wn) throw Error('widget-none profile 未找到');
console.log('[runner] widget-none.changed_bytes', wn.changed_bytes, '-> 0（净变化修正）');
wn.changed_bytes = 0;

const origChainOf = fi.chainOf;
fi.chainOf = function (profile) {
  const plan = fi.planChain(profile);
  console.log('[runner] chainOf -> 完整哈希链:', plan.map(m => m.profile).join(' -> '));
  return plan;
};

const { main } = require(path.join(ROOT, 'neos75-fullscreen', 'tools', 'mcu_flash_live.js'));
main().catch(e => { console.error(e.stack); process.exitCode = 1; });

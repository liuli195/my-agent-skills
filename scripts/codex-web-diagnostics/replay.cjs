// Offline only: no browser, network, prompt text or installation changes.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function replay(record, snapshotName = 'finalConflict') {
  const evidence = record.markdownConflict?.reconciliation ?? record.reconciliation;
  if (evidence?.schemaVersion !== 1 || evidence.captureFailed)
    throw Error('缺少完整的匹配取证记录');
  if (!['lastConsistent', 'firstConflict', 'finalConflict'].includes(snapshotName))
    throw Error('不支持的快照名称');
  const snapshot = evidence[snapshotName];
  if (!snapshot?.replayable) throw Error('快照缺失或已截断，不能作为完整重放证据');
  const source = fs.readFileSync(path.join(__dirname, '../../tests/fixtures/codex_web_markdown_6_1_2.cjs'), 'utf8');
  // Execute only the repository's frozen upstream matcher, never code from a log.
  const Stream = vm.runInNewContext(source + ';ur');
  const stream = new Stream();
  stream.committed = snapshot.committed;
  stream.latest = snapshot.latest;
  const choices = [];
  const original = stream.committedIndex;
  stream.committedIndex = function(block) {
    const chosen = original.call(this, block);
    choices.push({ observedIndex: choices.length, chosen: chosen ?? null });
    return chosen;
  };
  const result = stream.reconcile(snapshot.observed);
  return { snapshot: snapshotName, sequence: snapshot.sequence,
    consistent: Array.isArray(result), reason: result.diagnostic?.reason ?? null,
    pendingCount: Array.isArray(result) ? result.length : null, choices };
}
module.exports = { replay };
if (require.main === module) {
  try {
    if (process.argv.length < 3 || process.argv.length > 4)
      throw Error('用法：node replay.cjs <失败日志文件> [lastConsistent|firstConflict|finalConflict]');
    console.log(JSON.stringify(replay(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), process.argv[3]), null, 2));
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}

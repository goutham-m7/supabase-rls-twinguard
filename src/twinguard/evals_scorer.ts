// Authored TwinGuard adapter for the Supabase Evals ToolScorer contract.
import type { ToolScorer } from '@supabase-evals/core';

const spec = __SPEC__;
function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') {
    return '{' + Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => JSON.stringify(key) + ':' + canonical(item)).join(',') + '}';
  }
  return JSON.stringify(value);
}
const scorer: ToolScorer = async (ctx) => {
  const checks: { name: string; passed: boolean; message: string }[] = [];
  let repaired = true, isolated = true, writesDenied = true, valid = true;
  try {
    for (const [schema, table] of spec.tables) {
      const target = `"${schema}"."${table}"`;
      for (const actor of ['0', '1', 'anon']) {
        const role = actor === 'anon' ? 'anon' : 'authenticated';
        const sub = actor === 'anon' ? '' : spec.users[Number(actor)];
        const claims = JSON.stringify(sub ? { sub, role } : { role });
        const expected = actor === 'anon' ? [] : [Number(actor) * 2 + 1, Number(actor) * 2 + 2];
        const operations = [
          ['select', `SELECT id FROM ${target} ORDER BY id`],
          ['insert', `INSERT INTO ${target} VALUES (999, '${spec.tenants[0]}', 777) RETURNING id`],
          ['update', `UPDATE ${target} SET cents=cents+1 RETURNING id`],
          ['delete', `DELETE FROM ${target} RETURNING id`],
        ];
        for (const [operation, statement] of operations) {
          let ids: number[] = [], code: string | undefined;
          try {
            const result = await ctx.query(`BEGIN; SET LOCAL ROLE ${role};
              SET LOCAL request.jwt.claim.sub = '${sub}';
              SET LOCAL request.jwt.claims = '${claims}';
              ${statement}; ROLLBACK;`);
            ids = result.rows.map(row => Number(row.id));
          } catch (error) {
            code = error instanceof Error && 'code' in error ? String(error.code) : 'unknown';
          } finally {
            // Failed SQL transactions must be reset before the next identity.
            await ctx.query('ROLLBACK;');
          }
          valid &&= code === undefined || code === '42501';
          if (operation === 'select') {
            if (actor !== 'anon') repaired &&= code === undefined && expected.every(id => ids.includes(id));
            isolated &&= ids.every(id => expected.includes(id));
          } else {
            writesDenied &&= ids.length === 0;
          }
        }
      }
    }
    const state = (await ctx.query(spec.stateSql)).rows[0].state;
    const data = (await ctx.query(spec.dataSql)).rows[0].data;
    checks.push(
      { name: 'legitimate reads repaired', passed: repaired && valid, message: 'Both tenants, both schemas; unexpected errors fail closed' },
      { name: 'no unauthorized reads', passed: isolated && valid, message: 'Other tenant and anon remain denied' },
      { name: 'writes remain denied', passed: writesDenied && valid, message: 'INSERT/UPDATE/DELETE are independently rolled back' },
      { name: 'seeded data preserved', passed: canonical(data) === canonical(spec.data), message: 'Privileged fixture data comparison' },
      { name: 'audit-only state unchanged', passed: !spec.auditOnly || canonical(state) === canonical(spec.state), message: 'Fixture catalogs, ACLs, definitions and rows' },
    );
  } catch (error) {
    return { passed: false, checks: [{ name: 'scorer completed', passed: false, message: String(error) }] };
  }
  return { passed: checks.every(check => check.passed), checks };
};
export default scorer;

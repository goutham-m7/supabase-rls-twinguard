// Test-only adapter: Supabase Evals ctx.query contract over a real PG connection.
import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';
const lines = createInterface({ input: process.stdin })[Symbol.asyncIterator]();
const { default: scorer } = await import(pathToFileURL(process.argv[2]).href);
const query = async (sql) => {
  console.log(JSON.stringify({ sql }));
  const response = JSON.parse((await lines.next()).value);
  if (response.error) throw Object.assign(new Error(response.error), { code: response.code });
  return response;
};
const result = await scorer({ query });
console.log(JSON.stringify({ result }));
process.stdin.destroy();

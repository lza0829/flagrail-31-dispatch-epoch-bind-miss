export async function get(path) {
  const r = await fetch(`/api${path}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function post(path, body) {
  const r = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function postFixture(name) {
  const r = await fetch(`/api/装载/夹具?名=${encodeURIComponent(name)}`, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

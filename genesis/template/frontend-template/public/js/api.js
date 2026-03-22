export async function api(path) {
  try { const res = await fetch(path); return await res.json(); } catch (e) { return null; }
}

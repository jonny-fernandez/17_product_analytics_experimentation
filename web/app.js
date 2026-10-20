/* First-party, same-origin, consent-aware demo. No cookies, localStorage or analytics SDK. */
"use strict";
const ids = ["start", "view", "cart", "checkout", "purchase", "refresh"];
const controls = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
const consent = document.getElementById("consent");
const output = document.getElementById("result");
let session = null;
let stage = 0;
async function send(url, value) {
  const response = await fetch(url, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(value)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || result.reason || "Server rejected event");
  return result;
}
function show(value) { output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2); }
function next() {
  for (const id of ["view", "cart", "checkout", "purchase"]) controls[id].disabled = true;
  if (session && consent.checked && stage < 4) controls[["view", "cart", "checkout", "purchase"][stage]].disabled = false;
}
async function start() {
  if (!consent.checked) return show("Consent is required. Nothing was recorded.");
  try { session = await send("/api/start", {consent: true}); stage = 0; next(); show("Synthetic session created. Browser events are captured only after consent."); }
  catch (err) { show(err.message); }
}
async function step(name) {
  if (!session || !consent.checked) return show("Consent required.");
  const event = {
    schema_version: 1, event_id: "evt_" + crypto.randomUUID().replaceAll("-", ""),
    user_id: session.user_id, session_id: session.session_id,
    name, occurred_at: new Date().toISOString(), properties: {}
  };
  try { const result = await send("/api/event", event); stage++; next(); show(result); }
  catch (err) { show(err.message); }
}
controls.start.onclick = start;
controls.view.onclick = () => step("product_viewed");
controls.cart.onclick = () => step("cart_item_added");
controls.checkout.onclick = () => step("checkout_started");
controls.purchase.onclick = async () => {
  if (!session || !consent.checked) return;
  try { const result = await send("/api/purchase", {user_id:session.user_id, session_id:session.session_id}); stage = 4; next(); show(result); }
  catch (err) { show(err.message); }
};
controls.refresh.onclick = async () => {
  try { const res = await fetch("/api/status"); show(await res.json()); }
  catch (err) { show(err.message); }
};
consent.onchange = () => { if (!consent.checked) { session = null; stage = 4; show("Tracking stopped for this browser session. Prior synthetic records remain in the local SQLite file until deleted."); } next(); };

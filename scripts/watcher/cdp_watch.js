#!/usr/bin/env node
/* cdp_watch.js — DOM watcher for Qoder CN over the Chrome DevTools Protocol.
 *
 * WHY: our own finding #6 is that the client never persists the timeout banner
 * or per-request timing to any log. This watcher attaches to the running Qoder
 * CN renderer over CDP and stamps those transitions *from the outside*, giving
 * (a) high-resolution, client-perceived request lifecycle events and (b) an
 * independent record to cross-check against the runtime-log resume (80408)
 * timestamps. It also trips loudly if code 80411 "Input content too long" ever
 * renders — the error the service has never once shown.
 *
 * STATUS (2026-09-09) — the premise is partly superseded, and this instrument
 * needs an outer check. The runtime log DOES carry per-interaction timing
 * (`[ACPProgressStateMachine] State transition: …`, report §4.7) and the banner
 * event (the `"title":"resume"` tool call plus the `resume_tool_call` phase
 * transition), so the log stream is now the primary instrument and the DOM
 * stream the cross-check — not the other way round.
 *
 * KNOWN FALSE-POSITIVE CLASS (found on 2026-09-09): `scan()` reads the text of
 * the *last message bubble*, so any assistant reply that quotes a needle string
 * ("Response timeout. Click to resume", "Allocated quota exceeded", …) fires
 * `banner_on`, and ordinary words like "working"/"thinking" in reply text fire
 * `working`; a button labelled Continue/Retry/"try again" anywhere in the panel
 * fires `resume on=1`. Today's captures show 3 `banner_on` + 54 `working` with
 * zero matching `resume_tool_call` / `ActionRequired` / 80408 lines in the logs
 * for those instants — i.e. the watcher saw the report being written, not a
 * failure. Treat DOM events as candidate signals until the log stream confirms
 * them; a fix would be to match the banner only inside the status/notice element
 * rather than the message body.
 *
 * PRIVACY (non-negotiable, matches the repo's "transcripts withheld" policy and
 * the PII gate): the page-side observer records ONLY event type, timestamp, and
 * NUMERIC lengths plus a fixed banner LABEL drawn from a known whitelist. It
 * NEVER reads or transmits message text or any arbitrary DOM string.
 *
 * Zero dependencies: uses Node >=18 global fetch + global WebSocket.
 *
 *   node scripts/watcher/cdp_watch.js probe [--port 9222]   # discover targets
 *   node scripts/watcher/cdp_watch.js watch [--port 9222] [--target <substr>]
 *
 * Launch Qoder CN first:   qoder-cn --remote-debugging-port=9222
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ARGS = process.argv.slice(2);
const MODE = ARGS[0] || 'probe';
const PORT = (() => { const i = ARGS.indexOf('--port'); return i >= 0 ? ARGS[i + 1] : '9222'; })();
const TARGET_FILTER = (() => { const i = ARGS.indexOf('--target'); return i >= 0 ? ARGS[i + 1] : null; })();
const OUT = path.join(__dirname, 'out');
const BASE = `http://127.0.0.1:${PORT}`;

fs.mkdirSync(OUT, { recursive: true });

// ---- tiny CDP client over the global WebSocket (all bounded) ----------------
function connect(wsUrl, openMs = 4000) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 0, settled = false;
    const pending = new Map();
    const eventHandlers = [];
    const openTo = setTimeout(() => { if (!settled) { settled = true; try { ws.close(); } catch (_) {} reject(new Error('open timeout')); } }, openMs);
    ws.onopen = () => { if (!settled) { settled = true; clearTimeout(openTo); resolve(api); } };
    ws.onerror = (e) => { if (!settled) { settled = true; clearTimeout(openTo); reject(new Error('ws error: ' + (e && e.message))); } };
    ws.onclose = () => { if (!settled) { settled = true; clearTimeout(openTo); reject(new Error('ws closed')); }
                        else { for (const { rej } of pending.values()) rej(new Error('closed')); pending.clear(); } };
    ws.onmessage = (m) => {
      const msg = JSON.parse(m.data);
      if (msg.id && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id); pending.delete(msg.id);
        msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
      } else if (msg.method) {
        eventHandlers.forEach((h) => h(msg.method, msg.params));
      }
    };
    const api = {
      send(method, params = {}, ackMs = 6000) {
        return new Promise((res, rej) => {
          const n = ++id;
          const t = setTimeout(() => { if (pending.has(n)) { pending.delete(n); rej(new Error(method + ' timeout')); } }, ackMs);
          pending.set(n, { res: (v) => { clearTimeout(t); res(v); }, rej: (e) => { clearTimeout(t); rej(e); } });
          ws.send(JSON.stringify({ id: n, method, params }));
        });
      },
      on(fn) { eventHandlers.push(fn); },
      close() { try { ws.close(); } catch (_) {} },
    };
  });
}

async function listTargets() {
  const r = await fetch(`${BASE}/json`, { signal: AbortSignal.timeout(6000) });
  return (await r.json()).filter((t) => t.webSocketDebuggerUrl);
}

function localStamp(t) {
  const d = new Date(t);
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
         `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}

// ---- page-side observer (installed by `watch`) ------------------------------
const OBSERVER_SRC = `(function(){
  if (window.__QOS_INSTALLED) return 'already';
  window.__QOS_INSTALLED = true;
  window.__QOSQ = []; window.__QOS_state = {t:false,r:false,w:null,len:0};
  function root(){ return document.querySelector('.chat-panel-container') || document.querySelector('.agentchat-container') || null; }
  function aria(){ var a=document.querySelector('.monaco-aria-container')||document.querySelector('[aria-live]'); return a?(a.textContent||''):''; }
  var NEEDLES = [ ['timeout_80408','Response timeout. Click to resume'], ['tool_limit_40429','Tool usage limit reached'], ['input_too_long_80411','Input content too long'], ['quota_alloc','Allocated quota exceeded'], ['quota_week','has been exhausted'], ['access_denied','Access denied, please make sure your account'] ];
  var WORK = ['working','generating','thinking','stop','cancel','esc to cancel'];
  function vis(e){ return e && e.offsetParent !== null; }
  function push(ev, extra){ var o={ev:ev,t:Date.now(),pn:performance.now()}; for(var k in (extra||{})) o[k]=extra[k]; window.__QOSQ.push(o); }
  function lastMsg(){ var r=root(); if(!r) return null; var m=r.querySelectorAll('[class*=message]'); for(var i=m.length-1;i>=0;i--){ if(vis(m[i])) return m[i]; } return null; }
  function resumeBtn(){ var r=root(); if(!r) return false; var b=r.querySelectorAll('button,[role=button],a'); for(var i=0;i<b.length;i++){ if(vis(b[i])&&/resume|continue|retry|try again/i.test(b[i].textContent||'')) return true; } return false; }
  function scan(){
    var lm = lastMsg();
    if(!lm){ return; }                                              // chat panel not mounted -> no signals
    var lt = lm.innerText||''; var ll = lt.toLowerCase();
    // (1) outcome banner on the CURRENT turn only (scrollback ignored)
    var tHit=null; for(var i=0;i<NEEDLES.length;i++){ if(lt.indexOf(NEEDLES[i][1])>=0){ tHit=NEEDLES[i][0]; break; } }
    if(!!tHit !== window.__QOS_state.t){ window.__QOS_state.t=!!tHit; push(tHit?'banner_on':'banner_off', tHit?{banner:tHit}:{}); }
    // (2) actionable Resume control present == a live, unresolved interruption
    var rb = resumeBtn(); if(rb !== window.__QOS_state.r){ window.__QOS_state.r=rb; push('resume',{on:rb?1:0}); }
    // (3) working/streaming (chat text + aria status)
    var w = WORK.some(function(x){return (ll+' '+aria().toLowerCase()).indexOf(x)>=0;}); if(w!==window.__QOS_state.w){ window.__QOS_state.w=w; push('working',{on:w?1:0}); }
    // (4) current-turn length delta -> streaming/first-token progress (NUMERIC only, never text)
    var L = lt.length; if(L!==window.__QOS_state.len){ var d=L-window.__QOS_state.len; window.__QOS_state.len=L; push('turn_delta',{d:d,len:L}); }
  }
  try {
    var mo = new MutationObserver(function(){ if(!window.__QOS_p){window.__QOS_p=1; queueMicrotask(function(){window.__QOS_p=0; scan();});} });
    mo.observe(document.body, {subtree:true, childList:true, characterData:true, attributes:true});
  } catch(e){}
  setInterval(scan, 300);
  push('installed',{});
  return 'installed';
})()`;

const PROBE_EXPR = `(function(){var b=document.body?document.body.innerText:'';var q=function(s){try{return document.querySelectorAll(s).length}catch(e){return -1}};return JSON.stringify({href:location.href.slice(0,90),has:{timeout:b.indexOf('Response timeout. Click to resume')>=0,tool:b.indexOf('Tool usage limit')>=0,toolong:b.indexOf('Input content too long')>=0,quota:/quota|exhausted|Access denied/.test(b)},counts:{textarea:q('textarea'),edit:q('[contenteditable="true"]'),btn:q('button'),listitem:q('[role=listitem]'),msg:q('[class*=message]')},len:b.length})})()`;

async function doProbe() {
  let targets;
  try { targets = await listTargets(); }
  catch (e) { console.error('cannot reach CDP /json on port ' + PORT + ': ' + e.message); process.exit(2); }
  console.log(`found ${targets.length} CDP target(s); probing each in parallel, bounded per target...`);
  const rows = await Promise.all(targets.map(async (t) => {
    let api;
    const base = { id: t.id, type: t.type, title: (t.title || '').slice(0, 40), url: (t.url || '').slice(0, 60) };
    try {
      api = await connect(t.webSocketDebuggerUrl);
      await api.send('Runtime.enable', {}, 5000);
      const { result } = await api.send('Runtime.evaluate', { expression: PROBE_EXPR, returnByValue: true }, 6000);
      return Object.assign(base, JSON.parse(result.value));
    } catch (e) {
      return Object.assign(base, { error: String(e.message).slice(0, 60) });
    } finally { if (api) api.close(); }
  }));
  const file = path.join(OUT, `probe_${localStamp(Date.now()).replace(/[: ]/g, '')}.json`);
  fs.writeFileSync(file, JSON.stringify(rows, null, 1));
  console.log(JSON.stringify(rows, null, 1));
  console.log(`\n[saved ${path.relative(process.cwd(), file)}]  pick the chat target (highest counts.msg/listitem with has.timeout-capable UI) and run:  node ${path.relative(process.cwd(), __filename)} watch --target <substr>`);
}

async function doWatch() {
  let targets = await listTargets();
  targets = targets.filter((t) => t.type === 'page');   // renderer pages only; skip worker/shared-process targets that reject Runtime.enable
  if (TARGET_FILTER) targets = targets.filter((t) => (t.url + ' ' + (t.title || '')).includes(TARGET_FILTER));
  if (!targets.length) { console.error('no page CDP targets; is Qoder CN running with --remote-debugging-port and does --target match?'); process.exit(1); }
  const ts = localStamp(Date.now());
  const csvFile = path.join(OUT, `session_${ts.replace(/[: ]/g, '')}.csv`);
  const jsonlFile = csvFile.replace(/\.csv$/, '.jsonl');
  fs.writeFileSync(csvFile, 'local_ts,pn,target_id,event,banner,working,delta,len\n');
  console.log(`watching ${targets.length} target(s) -> ${path.relative(process.cwd(), csvFile)}  (Ctrl-C to stop)`);

  const sessions = [];
  for (const t of targets) {
    try {
      const api = await connect(t.webSocketDebuggerUrl);
      await api.send('Runtime.enable', {}, 5000);
      await api.send('Runtime.evaluate', { expression: OBSERVER_SRC, returnByValue: true }, 6000);
      sessions.push({ id: t.id, api });
      console.log(`attached+observing: ${t.type} ${t.id} ${(t.title || '').slice(0, 40)}`);
    } catch (e) { console.log(`skip ${t.type} ${t.id}: ${String(e.message).slice(0, 50)}`); }
  }
  if (!sessions.length) { console.error('no observerable page target (chat panel target not reached)'); process.exit(1); }

  const poll = setInterval(async () => {
    for (const s of sessions) {
      try {
        const { result } = await s.api.send('Runtime.evaluate', { expression: 'JSON.stringify(window.__QOSQ.splice(0))', returnByValue: true });
        const evs = result.value ? JSON.parse(result.value) : [];
        for (const e of evs) {
          fs.appendFileSync(jsonlFile, JSON.stringify(Object.assign({ target: s.id }, e)) + '\n');
          fs.appendFileSync(csvFile, `${localStamp(e.t)},${e.pn.toFixed(1)},${s.id},${e.ev},${e.banner || ''},${e.working != null ? e.working : ''},${e.d != null ? e.d : ''},${e.len != null ? e.len : ''}\n`);
          const tag = { banner_on: '***', banner_off: '   ', working: e.working ? ' >w' : ' <-', dom_delta: '  .', installed: ' ok' }[e.ev] || '  ?';
          console.log(`${localStamp(e.t)} ${tag} ${e.ev} ${e.banner || ''} ${e.working != null ? (e.working ? 'ON' : 'off') : ''}`);
        }
      } catch (_) { /* target navigated/closed; ignore this tick */ }
    }
  }, 400);

  process.on('SIGINT', () => { clearInterval(poll); sessions.forEach((s) => s.api.close()); console.log(`\nstopped. -> ${path.relative(process.cwd(), csvFile)} / ${path.basename(jsonlFile)}`); process.exit(0); });
}

async function doEval() {
  const xi = ARGS.indexOf('--expr'); const expr = xi >= 0 ? ARGS[xi + 1] : null;
  if (!expr) { console.error('eval needs --expr "<js returning a JSON string>"'); process.exit(1); }
  let targets = await listTargets();
  if (TARGET_FILTER) targets = targets.filter((t) => (t.url + ' ' + (t.title || '')).includes(TARGET_FILTER));
  targets = targets.filter((t) => t.type === 'page');   // structural eval is for renderers only
  for (const t of targets) {
    let api;
    try {
      api = await connect(t.webSocketDebuggerUrl);
      await api.send('Runtime.enable', {}, 5000);
      const { result } = await api.send('Runtime.evaluate', { expression: expr, returnByValue: true }, 8000);
      console.log(`--- ${t.type} ${t.id} ${(t.title || '').slice(0, 40)} ---`);
      console.log(typeof result.value === 'string' ? result.value : JSON.stringify(result.value));
    } catch (e) { console.log(`--- ${t.type} ${t.id} ERROR ${String(e.message).slice(0, 60)} ---`); }
    finally { if (api) api.close(); }
  }
}

async function doDrain() {
  // One-shot: connect to the chat page target(s), pull the queued events out of
  // window.__QOSQ (they keep their original in-page timestamps), append to disk,
  // exit. Designed to be run by an init/cron/systemd-timer, NOT a persistent
  // process, because this agent harness reaps any process a tool call spawns.
  let targets = (await listTargets()).filter((t) => t.type === 'page');
  if (TARGET_FILTER) targets = targets.filter((t) => (t.url + ' ' + (t.title || '')).includes(TARGET_FILTER));
  fs.mkdirSync(OUT, { recursive: true });
  const jf = path.join(OUT, 'events.jsonl'), cf = path.join(OUT, 'events.csv');
  if (!fs.existsSync(cf)) fs.writeFileSync(cf, 'local_ts,pn,target_id,event,banner,resume,working,delta,len\n');
  let n = 0;
  for (const t of targets) {
    let api;
    try {
      api = await connect(t.webSocketDebuggerUrl);
      await api.send('Runtime.enable', {}, 5000);
      // self-heal: re-install the observer if the renderer reloaded (__QOS_INSTALLED guard no-ops otherwise)
      await api.send('Runtime.evaluate', { expression: OBSERVER_SRC, returnByValue: true }, 6000);
      const { result } = await api.send('Runtime.evaluate', { expression: 'JSON.stringify(window.__QOSQ?window.__QOSQ.splice(0):[])', returnByValue: true }, 8000);
      const evs = result.value ? JSON.parse(result.value) : [];
      for (const e of evs) {
        if (e.ev === 'installed') continue;
        fs.appendFileSync(jf, JSON.stringify(Object.assign({ target: t.id }, e)) + '\n');
        const resumeCol = (e.ev === 'resume' && e.on != null) ? e.on : '';
        const workCol = (e.ev === 'working' && e.on != null) ? e.on : '';
        fs.appendFileSync(cf, `${localStamp(e.t)},${(e.pn || 0).toFixed(1)},${t.id},${e.ev},${e.banner || ''},${resumeCol},${workCol},${e.d != null ? e.d : ''},${e.len != null ? e.len : ''}\n`);
        n++;
      }
    } catch (_) { /* target transiently busy; retry next tick */ }
    finally { if (api) api.close(); }
  }
  console.log(`drained ${n} event(s) -> ${path.relative(process.cwd(), cf)}`);
}

async function doReload() {
  let targets = (await listTargets()).filter((t) => t.type === 'page');
  for (const t of targets) { let api; try { api = await connect(t.webSocketDebuggerUrl); await api.send('Page.enable', {}, 5000); await api.send('Page.reload', { ignoreCache: false }, 5000); console.log('reloaded ' + t.id); } catch (e) { console.log('reload ' + t.id + ': ' + String(e.message).slice(0, 50)); } finally { if (api) api.close(); } }
}

({ probe: doProbe, watch: doWatch, eval: doEval, drain: doDrain, reload: doReload })[MODE]().catch((e) => { console.error(String(e.stack || e).slice(0, 400)); process.exit(1); });

// Real isolated Chromium/WebGL smoke. Uses synthetic fixes, never device GPS.
// node tool/map_browser_smoke.cjs [http://127.0.0.1:5501]
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const profile = path.join(root, 'build/map-smoke-profile');
const base = process.argv[2] || 'http://127.0.0.1:5501';
const chromePath = process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

class CDP {
  constructor(socket) {
    this.socket = socket; this.id = 0; this.pending = new Map(); this.errors = [];
    socket.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const item = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) item?.reject(new Error(message.error.message));
        else item?.resolve(message.result);
      } else if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') {
        this.errors.push(message.params.args.map(arg => arg.value ?? arg.description ?? '').join(' ').slice(0, 600));
      } else if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) {
        this.errors.push(`${message.params.response.status} ${message.params.response.url}`);
      }
    });
  }
  call(method, params = {}, sessionId) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params, sessionId }));
    });
  }
  async evaluate(expression, session) {
    const result = await this.call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, session);
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result.value;
  }
}

(async () => {
  await fs.mkdir(profile, { recursive: true });
  await fs.rm(path.join(profile, 'DevToolsActivePort'), { force: true });
  const chrome = spawn(chromePath, ['--headless=new', '--use-angle=swiftshader',
    '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check',
    '--window-size=390,844', `--user-data-dir=${profile}`, 'about:blank'],
    { windowsHide: true, stdio: 'ignore' });
  let cdp;
  try {
    let port;
    for (let i = 0; i < 60; i++) {
      try { port = Number((await fs.readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]); break; }
      catch { await sleep(250); }
    }
    assert.ok(port, 'Chromium remote debugging did not start');
    const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
    const socket = new WebSocket(version.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.addEventListener('open', resolve); socket.addEventListener('error', reject); });
    cdp = new CDP(socket);
    const { targetId } = await cdp.call('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await cdp.call('Target.attachToTarget', { targetId, flatten: true });
    await cdp.call('Page.enable', {}, sessionId);
    await cdp.call('Runtime.enable', {}, sessionId);
    await cdp.call('Network.enable', {}, sessionId);
    await cdp.call('Emulation.setDeviceMetricsOverride', { width: 390, height: 760, deviceScaleFactor: 1, mobile: true }, sessionId);
    const apiBase = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
    await cdp.call('Page.navigate', { url: `${base}/map_embed.html?api=${encodeURIComponent(apiBase)}` }, sessionId);
    let ready = false;
    for (let i = 0; i < 90; i++) {
      ready = await cdp.evaluate('typeof mapReady !== "undefined" && mapReady', sessionId);
      if (ready) break;
      await sleep(500);
    }
    assert.ok(ready, `Map never became ready: ${cdp.errors.join('; ')}`);
    const apiCheck = await cdp.evaluate(`(async () => {
      const health = await fetch(${JSON.stringify(apiBase + '/v1/health')});
      const planning = await fetch(${JSON.stringify(apiBase + '/v1/trips/00000000-0000-0000-0000-000000000001/planning-requests')}, {
        method:'POST', headers:{'Content-Type':'application/json',
          'Idempotency-Key':'synthetic-ui-network-check','X-Correlation-ID':'ui-network-smoke'},
        body:JSON.stringify({target_count:1,constraint_overrides:{}})
      });
      return {health:health.status,protectedPlanning:planning.status};
    })()`, sessionId);
    assert.equal(apiCheck.health, 200);
    assert.equal(apiCheck.protectedPlanning, 401);
    // The expected unauthorized response is the sole allowed HTTP error in this smoke.
    cdp.errors = cdp.errors.filter(error => !error.startsWith('401 ')
      && !error.startsWith('Failed to load resource: the server responded with a status of 401'));
    const result = await cdp.evaluate(`new Promise(resolve => {
      window.__originalMap = map;
      window.__mapReloads = 0;
      map.on('load', () => window.__mapReloads++);
      for (let i = 0; i < 30; i++) window.postMessage(JSON.stringify({
        type: 'setUserLocation', latitude: 16.06 + i / 100000, longitude: 108.22,
        follow: true, recenter: i === 0
      }), window.location.origin);
      setTimeout(() => resolve({sameMap: map === window.__originalMap,
        reloads: window.__mapReloads, latitude: userMarker.getLngLat().lat,
        styleLoaded: map.isStyleLoaded(), tilesLoaded: map.areTilesLoaded()}), 1200);
    })`, sessionId);
    for (let i = 0; i < 40 && !result.tilesLoaded; i++) {
      await sleep(500);
      const status = await cdp.evaluate('({styleLoaded:map.isStyleLoaded(),tilesLoaded:map.areTilesLoaded()})', sessionId);
      Object.assign(result, status);
    }
    console.log(JSON.stringify({phase: 'afterSyntheticFixes', ...result, errors: cdp.errors}));
    assert.equal(result.sameMap, true);
    assert.equal(result.reloads, 0);
    assert.ok(Math.abs(result.latitude - 16.06029) < 0.000001);
    assert.equal(result.styleLoaded, true);
    assert.equal(result.tilesLoaded, true);
    const restarted = await cdp.evaluate(`new Promise(resolve => {
      const send = message => window.postMessage(JSON.stringify(message), window.location.origin);
      send({type:'clearUserLocation'});
      setTimeout(() => {
        const cleared = !userMarker;
        send({type:'setUserLocation', latitude:16.06029, longitude:108.22, follow:true, recenter:true});
        setTimeout(() => resolve({cleared, sameMap:map === window.__originalMap,
          latitude:userMarker?.getLngLat().lat, reloads:window.__mapReloads}), 800);
      }, 100);
    })`, sessionId);
    assert.equal(restarted.cleared, true);
    assert.equal(restarted.sameMap, true);
    assert.equal(restarted.reloads, 0);
    assert.ok(Math.abs(restarted.latitude - 16.06029) < 0.000001);
    const outside = await cdp.evaluate(`new Promise(resolve => {
      const before = map.getCenter().toArray();
      window.postMessage(JSON.stringify({type:'setUserLocation', latitude:21.03,
        longitude:105.85, follow:true, recenter:true}), window.location.origin);
      setTimeout(() => resolve({before, after:map.getCenter().toArray()}), 800);
    })`, sessionId);
    assert.deepEqual(outside.after, outside.before);
    assert.deepEqual(cdp.errors, [], 'PMTiles must actually load without console errors');
    const image = await cdp.call('Page.captureScreenshot', { format: 'png' }, sessionId);
    const screenshot = path.join(root, 'build/ui-review/map-browser-390.png');
    await fs.mkdir(path.dirname(screenshot), { recursive: true });
    await fs.writeFile(screenshot, Buffer.from(image.data, 'base64'));
    console.log(JSON.stringify({ ...result, ...apiCheck, gpsRestarted: true,
      outsideCameraStable: true, errors: cdp.errors, screenshot }));
  } finally {
    if (cdp) cdp.socket.close();
    if (chrome.pid) spawnSync('taskkill', ['/PID', String(chrome.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });

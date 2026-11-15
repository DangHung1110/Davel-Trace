const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../web/map_embed.html'), 'utf8');
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)]
  .map(match => match[1]).find(text => text.includes('function setUserLocation'));

function fixture() {
  const maps = [], markers = [], listeners = {}, messages = [], errors = [];
  class Map {
    constructor() { this.handlers = {}; this.cameras = []; maps.push(this); }
    on(event, handler) { (this.handlers[event] ??= []).push(handler); }
    emit(event, payload = {}) { for (const handler of this.handlers[event] ?? []) handler(payload); }
    addControl() {}
    getLayer() { return true; }
    easeTo(camera) { this.cameras.push(camera); }
  }
  class Marker {
    constructor() { markers.push(this); this.removed = false; }
    setLngLat(point) { this.point = [...point]; return this; }
    addTo() { return this; }
    remove() { this.removed = true; }
  }
  const parent = { postMessage: message => messages.push(JSON.parse(message)) };
  const window = { location: { origin: 'http://localhost:5501', search: '' }, parent,
    addEventListener: (event, handler) => { listeners[event] = handler; } };
  const context = vm.createContext({ window, document: {
    baseURI: 'http://localhost:5501/map_embed.html',
    getElementById: () => ({ style: {}, hidden: false }), createElement: () => ({ style: {} }),
  }, maplibregl: { Map, Marker, addProtocol() {}, NavigationControl: class {}, FullscreenControl: class {} },
  pmtiles: { Protocol: class { tile() {} } }, basemaps: { layers: () => [], namedFlavor: () => ({}) },
  URL, URLSearchParams, performance: { now: () => 0 }, cancelAnimationFrame() {}, requestAnimationFrame() {},
  console: { error: (...args) => errors.push(args) },
  });
  vm.runInContext(script, context);
  const send = (data, extra = {}) => listeners.message({ data: JSON.stringify(data),
    origin: window.location.origin, source: parent, ...extra });
  return { map: maps[0], markers, messages, errors, send };
}

test('latest location waits for map readiness and then moves on every fix', () => {
  const f = fixture();
  f.send({ type: 'setUserLocation', latitude: 16.05, longitude: 108.2, follow: true });
  f.send({ type: 'setUserLocation', latitude: 16.0502, longitude: 108.2002, follow: true });
  assert.equal(f.markers.length, 0);
  f.map.emit('load');
  assert.deepEqual(f.markers[0].point, [108.2002, 16.0502]);
  assert.equal(f.map.cameras.at(-1).zoom, 16);
  f.send({ type: 'setUserLocation', latitude: 16.0504, longitude: 108.2004, follow: true });
  assert.equal(f.markers.length, 1);
  assert.deepEqual(f.markers[0].point, [108.2004, 16.0504]);
  assert.equal(f.map.cameras.at(-1).zoom, undefined);
  assert.deepEqual(f.errors, []);
});

test('manual pan releases camera while marker keeps moving; recenter restores it', () => {
  const f = fixture(); f.map.emit('load');
  f.send({ type: 'setUserLocation', latitude: 16.05, longitude: 108.2, follow: true });
  f.map.emit('dragstart', { originalEvent: {} });
  assert.equal(f.messages.at(-1).type, 'mapUserPan');
  const calls = f.map.cameras.length;
  f.send({ type: 'setUserLocation', latitude: 16.06, longitude: 108.21, follow: false });
  assert.deepEqual(f.markers[0].point, [108.21, 16.06]);
  assert.equal(f.map.cameras.length, calls);
  f.send({ type: 'setUserLocation', latitude: 16.06, longitude: 108.21, follow: true, recenter: true });
  assert.equal(f.map.cameras.at(-1).zoom, 16);
});

test('clear removes live marker and clears a fix pending before map load', () => {
  const f = fixture();
  f.send({ type: 'setUserLocation', latitude: 16.05, longitude: 108.2 });
  f.send({ type: 'clearUserLocation' }); f.map.emit('load');
  assert.equal(f.markers.length, 0);
  f.send({ type: 'setUserLocation', latitude: 16.05, longitude: 108.2 });
  f.send({ type: 'clearUserLocation' });
  assert.equal(f.markers[0].removed, true);
});

test('wrong origin/source and invalid coordinates cannot create or move a marker', () => {
  const f = fixture(); f.map.emit('load');
  const data = { type: 'setUserLocation', latitude: 16.05, longitude: 108.2 };
  f.send(data, { origin: 'https://other.example' });
  f.send(data, { source: {} });
  f.send({ ...data, latitude: 91 }); f.send({ ...data, longitude: null });
  assert.equal(f.markers.length, 0);
  f.send(data); assert.equal(f.markers.length, 1);
});

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const listeners = new Map();
const elements = new Map();
const requests = [];
const toastMessages = [];
let tickerCallback = null;
let clock = 1_000_000;
const store = new Map();

function element(selector, values = {}) {
  const node = {
    value: '', disabled: false, innerHTML: '', textContent: '', style: {}, dataset: {},
    listeners: {}, classList: { toggle() {}, add() {}, remove() {} },
    addEventListener(name, callback) { this.listeners[name] = callback; },
    ...values,
  };
  elements.set(selector, node);
  return node;
}

const customMinutes = element('#customMinutes', { value: '10' });
const timerStart = element('#timerStart');
const timerStop = element('#timerStop');
const timerReset = element('#timerReset');
const timerDisplay = element('#timerDisplay');
const timerStatus = element('#timerStatus');
const ringProgress = element('#focusRing .ring-progress');
const focusSubject = element('#focusSubject', { value: '' });
element('#toastStack', { append(node) { toastMessages.push(node.textContent); }, remove() {} });
element('meta[name="csrf-token"]', { content: 'test-token' });

class TestDate extends Date {
  static now() { return clock; }
}

const document = {
  documentElement: { dataset: {} }, body: { dataset: {} }, activeElement: null,
  querySelector(selector) { return elements.get(selector) || null; },
  querySelectorAll() { return []; },
  createElement() { return { className: '', textContent: '', remove() {} }; },
  addEventListener(name, callback) { listeners.set(name, callback); },
};

const context = {
  document, Date: TestDate, Headers, FormData,
  matchMedia: () => ({ matches: false }),
  localStorage: { getItem() { return null; }, setItem() {} },
  sessionStorage: {
    getItem(key) { return store.get(key) || null; },
    setItem(key, value) { store.set(key, value); },
    removeItem(key) { store.delete(key); },
  },
  navigator: {},
  location: { href: '' },
  console,
  setTimeout, clearTimeout,
  setInterval(callback) { tickerCallback = callback; return 1; },
  clearInterval() { tickerCallback = null; },
  requestAnimationFrame(callback) { return setTimeout(callback, 0); },
  cancelAnimationFrame: clearTimeout,
  fetch: async (url, options) => {
    requests.push({ url, options });
    return { ok: true, status: 200, json: async () => ({ id: 42 }) };
  },
};
vm.runInNewContext(fs.readFileSync('app/static/js/studyx.js', 'utf8'), context);

async function main() {
  customMinutes.listeners.input({ target: customMinutes });
  timerStart.listeners.click();
  assert.match(timerStart.innerHTML, /Pause focus/);
  assert.equal(timerStatus.textContent, 'FOCUS IN PROGRESS');
  assert.equal(timerStop.disabled, false);

  clock += 60_000;
  timerStart.listeners.click();
  assert.equal(timerDisplay.textContent, '09:00', 'the clock should count down from elapsed time');
  assert.match(timerStart.innerHTML, /Resume focus/);
  assert.equal(timerStatus.textContent, 'PAUSED · TAKE YOUR TIME');
  assert.match([...store.values()][0], /"status":"paused"/);

  clock += 120_000;
  timerStart.listeners.click();
  assert.match(timerStart.innerHTML, /Pause focus/);
  clock += 120_000;
  timerStop.listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  await new Promise(resolve => setTimeout(resolve, 0));

  const saved = requests.find(request => request.url === '/api/focus-sessions');
  assert.ok(saved, `finishing a timer should save a focus session; requests=${JSON.stringify(requests.map(row => row.url))}; state=${timerStatus.textContent}; toast=${toastMessages.join('|')}`);
  const payload = JSON.parse(saved.options.body);
  assert.equal(payload.planned_minutes, 10);
  assert.equal(payload.actual_minutes, 3);
  assert.equal(payload.status, 'stopped');
  assert.ok(new Date(payload.ended_at) > new Date(payload.started_at));
  assert.equal(timerStatus.textContent, 'READY WHEN YOU ARE');
  assert.equal(timerDisplay.textContent, '10:00');
  assert.equal(timerStop.disabled, true);
  assert.equal(store.size, 0, 'saved timer state should be cleared');

  customMinutes.value = '1';
  customMinutes.listeners.input({ target: customMinutes });
  timerStart.listeners.click();
  clock += 60_000;
  tickerCallback();
  await new Promise(resolve => setTimeout(resolve, 0));
  await new Promise(resolve => setTimeout(resolve, 0));
  const completed = requests.filter(request => request.url === '/api/focus-sessions')[1];
  assert.ok(completed, 'the timer should save automatically when it reaches zero');
  const completedPayload = JSON.parse(completed.options.body);
  assert.equal(completedPayload.actual_minutes, 1);
  assert.equal(completedPayload.status, 'completed');
  assert.ok(toastMessages.includes('Focus session complete and saved to your calendar.'), 'completion should be clearly confirmed after saving');
  assert.equal(timerStatus.textContent, 'SESSION COMPLETE · SAVED');
  assert.equal(timerDisplay.textContent, '00:00');
  assert.match(timerStart.innerHTML, /Start another focus/);
  console.log('Timer UI start, pause, resume, finish and SQLite API save: passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });

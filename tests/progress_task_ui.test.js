'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const appRoot = path.join(__dirname, '..');
const js = fs.readFileSync(path.join(appRoot, 'app/static/js/studyx.js'), 'utf8');
const css = fs.readFileSync(path.join(appRoot, 'app/static/css/studyx-fixes.css'), 'utf8');
const esc = value => String(value).replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

// Exercise the actual helper from the bundled browser script without third-party dependencies.
const start = js.indexOf('  function taskCheckbox(item) {');
const end = js.indexOf('\n  }\n\n', start);
assert.ok(start >= 0 && end > start, 'Task checkbox helper must exist.');
const helperSource = js.slice(start, end + 4);
const taskCheckbox = new Function('esc', `${helperSource};return taskCheckbox`)(esc);

test('new task renders a visible, accessible unchecked checkbox', () => {
  const html = taskCheckbox({ id: 7, title: 'Math & Algebra', status: 'todo' });
  assert.match(html, /type="checkbox"/);
  assert.match(html, /data-toggle-task="7"/);
  assert.match(html, /aria-label="Complete Math &amp; Algebra"/);
  assert.ok(!html.includes(' checked '));
  assert.match(html, /<svg/);
});

test('completed task persists checked state in rendered checkbox', () => {
  const html = taskCheckbox({ id: 8, title: 'Geometry', status: 'done' });
  assert.match(html, /data-toggle-task="8" checked/);
  assert.match(html, /aria-label="Reopen Geometry"/);
  assert.match(css, /input\.task-check:checked \+ \.task-box svg/);
});

test('shared checkbox is used in dashboard and assignments, saves before reloading', () => {
  assert.equal((js.match(/\$\{taskCheckbox\(item\)\}/g) || []).length, 2);
  const changeIndex = js.indexOf("document.addEventListener('change', async event => {\n    const box = event.target.closest('input[data-toggle-task]');");
  assert.ok(changeIndex >= 0);
  const saveIndex = js.indexOf("api(`/assignments/${Number(box.dataset.toggleTask)}`", changeIndex);
  const reloadIndex = js.indexOf('window.location.reload();', changeIndex);
  assert.ok(saveIndex > changeIndex && reloadIndex > saveIndex);
  assert.match(js.slice(changeIndex, reloadIndex), /if \(!result\) \{ box\.checked = !completed/);
});

test('progress page renders courses from API including zero-minute courses', () => {
  assert.match(js, /data\.by_subject\.length/);
  assert.match(js, /data-progress-course/);
  assert.match(js, /assignments_completed/);
  assert.match(js, /progressCourseCount/);
  assert.match(js, /cache: 'no-store'/);
});

test('calendar assignment events expose the linked assignment status and checkbox', () => {
  const api = fs.readFileSync(path.join(appRoot, 'app/routes/api.py'), 'utf8');
  assert.match(api, /if item\.source_type == "assignment" and item\.source_id:/);
  assert.match(api, /result\["assignment_id"\] = assignment\.id/);
  assert.match(api, /result\["status"\] = assignment\.status/);
  assert.match(js, /taskCheckbox\(\{id: item\.assignment_id, title: item\.title, status: item\.status\}\)/);
  assert.match(js, /item\.assignment_id \? taskCheckbox/);
});

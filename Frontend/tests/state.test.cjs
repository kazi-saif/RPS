// Pure state tests: no browser or project data is accessed.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function fixture() {
  const elements = new Map();
  class Element {
    constructor() { this.listeners = {}; this.value = ''; this.textContent = ''; this.innerHTML = ''; this.hidden = false; this.open = false; }
    addEventListener(type, callback, options) { (this.listeners[type] ??= []).push({ callback, once: options?.once }); }
    emit(type) { const handlers = [...(this.listeners[type] ?? [])]; this.listeners[type] = handlers.filter(x => !x.once); for (const h of handlers) h.callback(); }
    showModal() { this.open = true; }
    close(value) { this.returnValue = value ?? this.returnValue; this.open = false; this.emit('close'); }
    reset() { this.value = ''; }
    querySelector() { return get('submit'); }
  }
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const requests = [];
  const context = vm.createContext({
    document: { getElementById: get },
    sessionStorage: { getItem: () => null, removeItem: () => {}, setItem: () => {} },
    window: { addEventListener: () => {} },
    fetch: async (...args) => { requests.push(args); return { ok: true, status: 200, json: async () => ({}) }; },
    FormData: class {}, URLSearchParams, console, Event: class {},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8'), context);
  return { context, get, requests, run: source => vm.runInContext(source, context) };
}

test('confirm and cancel resolve without native browser popups', async () => {
  const f = fixture();
  const canceled = f.run("confirmAction('Keep this private')");
  assert.equal(f.get('confirmText').textContent, 'Keep this private');
  f.get('confirmCancel').onclick();
  assert.equal(await canceled, false);
  const confirmed = f.run("confirmAction('Publish?')");
  f.get('confirmYes').onclick();
  assert.equal(await confirmed, true);
  const escaped = f.run("confirmAction('Leave?')");
  f.get('confirmation').close('cancel');
  assert.equal(await escaped, false);
});

test('cancel preserves unsaved marks; confirm discards them', async () => {
  const f = fixture(); f.run("dirtyMarks.add('S001')");
  let answer = f.run('discardUnsavedMarks()');
  f.get('confirmCancel').onclick();
  assert.equal(await answer, false);
  assert.equal(f.run('dirtyMarks.size'), 1);
  answer = f.run('discardUnsavedMarks()');
  f.get('confirmYes').onclick();
  assert.equal(await answer, true);
  assert.equal(f.run('dirtyMarks.size'), 0);
});

test('forced sign-out clears dirty marks and open dialogs', async () => {
  const f = fixture();f.run("token='expired';me={role:'teacher'};dirtyMarks.add('S001')");
  const pending = f.run("confirmAction('Leave?')");
  await f.run('logout(true)');
  assert.equal(await pending, false);
  assert.equal(f.run('token'), null);
  assert.equal(f.run('dirtyMarks.size'), 0);
  assert.equal(f.get('portal').hidden, true);
});

test('a stale unauthorized response does not sign out a newer login', async () => {
  const f = fixture();let reply;
  f.context.fetch = () => new Promise(resolve => { reply = resolve; });
  f.run("token='old'");const request = f.run("api('/me')");f.run("token='new'");
  reply({ok:false,status:401,json:async()=>({detail:'Expired'})});
  await assert.rejects(request, /Expired/);
  assert.equal(f.run('token'), 'new');
});

test('invalid server responses show a readable message', async () => {
  const f = fixture();
  f.context.fetch = async () => ({ok:false,status:500,json:async()=>{throw Error('not JSON');}});
  await assert.rejects(f.run("api('/students')"), /server could not complete/);
  f.context.fetch = async () => ({ok:false,status:404,json:async()=>({detail:'Not Found'})});
  await assert.rejects(f.run("api('/cohorts')"), /Restart the app server/);
});

test('review dialogs can stay open for a CSV preview step', async () => {
  const f = fixture();f.run("dialog('Preview','',async()=>false)");
  const button = {disabled:false};
  await f.get('editForm').onsubmit({preventDefault(){},submitter:button,target:{}});
  assert.equal(f.get('editor').open, true);
  assert.equal(button.disabled, false);
});

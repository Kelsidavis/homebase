import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../ui/app.js', import.meta.url), 'utf8');
const plexSource = source.slice(source.indexOf('const plexv = {'), source.indexOf('/* ==================================================================== loading */'));

// Run the Plex view with controlled network responses and timers. Focus and playback requests are observable
// without a Plex server, mpv or a browser; the dialog stands in for the remote's currently selected button.
function setup({ viewOffset = 0 } = {}) {
  const nodes = new Map();
  const timers = new Map();
  const intervals = new Map();
  const requests = [];
  const state = { view: 'plex', dialogOpen: false, settings: {} };
  const document = { activeElement: null };
  let timerId = 0;
  let dialog;
  let resolveMetadata;
  const metadata = new Promise((resolve) => { resolveMetadata = resolve; });
  const watched = { ratingKey: '101', type: 'episode', title: 'Finished episode', parentIndex: 1, index: 1, viewOffset };
  const next = { key: '102', title: 'Next episode', season: 1, episode: 2, show: 'Test show' };

  const node = (props = {}) => ({
    ...props,
    style: {},
    classList: { add() {} },
    replaceChildren() {},
    focus() { document.activeElement = this; },
  });
  const context = vm.createContext({
    state, document,
    $(selector) { return nodes.get(selector); },
    h(tag, props) {
      const el = node(props);
      if (props?.id) nodes.set(`#${props.id}`, el);
      return el;
    },
    music: { plex: () => metadata, thumb: () => null },
    fmtTime: () => '1:00',
    setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
    setInterval(callback) { intervals.set(++timerId, callback); return timerId; },
    clearInterval(id) { intervals.delete(id); },
    openDialog(options) {
      state.dialogOpen = true;
      dialog = options;
      document.activeElement = node({ onclick: options.actions.find((action) => action.primary).onClick });
    },
    closeDialog() { state.dialogOpen = false; dialog.onClose(); },
    async api(path, body) { requests.push({ path, body }); },
    starting: { show() {}, untilPlaying() {}, hide() {} },
    toast(message) { assert.fail(message); },
  });
  vm.runInContext(`${plexSource}\nglobalThis.views = { plexv, upNext };`, context);
  const { plexv, upNext } = context.views;
  plexv.render = () => {};
  plexv.watchPlayer = () => {};
  plexv.stack.push({ kind: 'item', key: watched.ratingKey });

  return {
    state, document, requests, next, watched, plexv, upNext, nodes,
    render: () => plexv.renderItem(node(), { key: watched.ratingKey }),
    finishMetadata() { resolveMetadata({ Metadata: [watched] }); },
    flushFocus() { for (const callback of timers.values()) callback(); timers.clear(); },
    tick() { for (const callback of [...intervals.values()]) callback(); },
    showNext() { upNext.chain = 3; upNext.show(next); },
  };
}

for (const viewOffset of [0, 120000]) {
  test(`Up next keeps focus when the finished episode refreshes (offset ${viewOffset})`, async () => {
    const app = setup({ viewOffset });
    const rendering = app.render();
    app.showNext();
    const playNow = app.document.activeElement;
    app.finishMetadata();
    await rendering;
    app.flushFocus();

    assert.equal(app.document.activeElement, playNow);
    app.document.activeElement.onclick();
    await Promise.resolve();
    assert.equal(app.requests.length, 1);
    assert.equal(app.requests[0].path, '/api/plex/play');
    assert.equal(app.requests[0].body.key, app.next.key);
  });
}

test('Up next keeps focus when it opens after the page schedules its focus', async () => {
  const app = setup();
  app.finishMetadata();
  await app.render();
  app.showNext();
  const playNow = app.document.activeElement;
  app.flushFocus();
  assert.equal(app.document.activeElement, playNow);
});

test('Opening episode details still focuses Play outside the dialog', async () => {
  const app = setup();
  app.finishMetadata();
  await app.render();
  app.flushFocus();
  assert.equal(app.document.activeElement, app.nodes.get('#plex-play'));
});

test('A delayed Plex refresh does not take focus after leaving Plex', async () => {
  const app = setup();
  app.finishMetadata();
  await app.render();
  app.state.view = 'home';
  app.flushFocus();
  assert.equal(app.document.activeElement, null);
});

test('The Up next countdown still starts the next episode', async () => {
  const app = setup();
  app.upNext.show(app.next);
  for (let seconds = 0; seconds < 10; seconds += 1) app.tick();
  await Promise.resolve();
  assert.equal(app.requests.length, 1);
  assert.equal(app.requests[0].body.key, app.next.key);
});

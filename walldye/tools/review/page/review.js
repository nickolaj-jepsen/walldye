// biome-ignore-all lint/suspicious/noAssignInExpressions: `(e.x ||= {})` chains build the nested review state.
// biome-ignore-all lint/suspicious/noFocusedTests: `fit()` sizes the picture; this is not a test file.
// CFG comes from review/state.py config(); the state shape is documented on load_state().

const { steps: STEPS, pieces: PIECES, taxonomy: TAXONOMY, labels: LABELS } = CFG;
const { themes: THEMES, canvas: CANVAS, facets: FACETS, text: TEXT } = CFG;
// Actual pixels means a 16:9 piece 2560 device pixels wide; other shapes scale alike.
const ZOOM_WIDTH = 2560;

const state = CFG.state || {};
const view = { i: 0, aspect: '16:9', theme: THEMES[0].name, comparing: false, zoom: false };
let noteAdvances = false;
const lints = {};
const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k === 'value') e.value = v;
    else if (k.startsWith('on')) e[k] = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  e.append(...children.filter((c) => c != null && c !== false && c !== ''));
  return e;
}

// --- state ---------------------------------------------------------------------------------

let saveTimer = null;
function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flush, 200);
}
async function flush() {
  clearTimeout(saveTimer);
  await fetch('state', { method: 'POST', body: JSON.stringify(state) });
}

// Empty objects go; empty lists stay, since an emptied facet is an edit.
function prune(o) {
  for (const [k, v] of Object.entries(o)) {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      prune(v);
      if (!Object.keys(v).length) delete o[k];
    }
  }
}
function update(slug, fn) {
  const e = structuredClone(state[slug] || {});
  fn(e);
  prune(e);
  if (Object.keys(e).length) state[slug] = e;
  else delete state[slug];
  save();
}

const entryOf = (slug) => state[slug] || {};
const piece = (slug) => PIECES[slug];
const cur = () => STEPS[view.i];
const decisionOf = (s) => entryOf(s.slug).versions?.[s.variant] || {};
const statusOf = (s) => decisionOf(s).status || '';
const hasVersions = (slug) => Object.keys(piece(slug).versions).length > 1;
const aspectsOf = (s) => piece(s.slug).versions[s.variant].aspects;
const sameList = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

function setDecision(s, key, value) {
  update(s.slug, (e) => {
    const d = ((e.versions ||= {})[s.variant] ||= {});
    if (value) d[key] = value;
    else delete d[key];
  });
}

// A named version of a removed new piece is not asked about.
function isMoot(s) {
  if (s.variant === 'default') return false;
  const d = STEPS.find((t) => t.slug === s.slug && t.variant === 'default');
  return !!d && !d.published && statusOf(d) === 'drop';
}

function kindOf(s) {
  if (s.published) return 'On the site';
  return s.variant === 'default' ? 'New piece' : 'New version';
}

function kindLine(s) {
  const edit = 'edit sends it back to the agent with your note';
  if (!s.published && s.variant === 'default')
    return `A new piece. Accept publishes it; ${edit}; remove leaves it a draft, to be deleted.`;
  if (!s.published)
    return `A new version of this piece. Accept publishes it; ${edit}; remove leaves it a draft.`;
  if (s.variant === 'default')
    return `On the site. Accept changes nothing; ${edit}; unpublish hides the piece and all its versions.`;
  return `On the site. Accept changes nothing; ${edit}; unpublish hides this version.`;
}

// What the step's decision is called: the published versions are unpublished, not removed.
function wordOf(s, st) {
  return { keep: 'accept', edit: 'edit', drop: s.published ? 'unpublish' : 'remove' }[st];
}

function nameOf(s) {
  const title = text(s.slug, 'title') || s.slug;
  if (!hasVersions(s.slug)) return title;
  return `${title} · ${versionText(s.slug, s.variant, 'label') || s.variant}`;
}

// --- words and facets ---------------------------------------------------------------------

const edits = (slug) => entryOf(slug).edits || {};
const hasEdits = (slug) => ['edits', 'facets', 'labels'].some((k) => k in entryOf(slug));

function text(slug, key) {
  const e = edits(slug);
  return key in e ? e[key] : piece(slug)[key];
}
function setText(slug, key, value) {
  update(slug, (e) => {
    const ed = (e.edits ||= {});
    if (value === piece(slug)[key]) delete ed[key];
    else ed[key] = value;
  });
  edited(slug);
}

function versionText(slug, name, key) {
  const v = edits(slug).variants?.[name] || {};
  return key in v ? v[key] : piece(slug).versions[name][key];
}
function setVersionText(slug, name, key, value) {
  update(slug, (e) => {
    const v = (((e.edits ||= {}).variants ||= {})[name] ||= {});
    if (value === piece(slug).versions[name][key]) delete v[key];
    else v[key] = value;
  });
  edited(slug);
}

function facetList(slug, f) {
  const e = edits(slug);
  return f in e ? e[f] : piece(slug)[f];
}
function setFacetList(slug, f, list) {
  update(slug, (e) => {
    const ed = (e.edits ||= {});
    if (sameList(list, piece(slug)[f])) delete ed[f];
    else ed[f] = list;
  });
  edited(slug);
}

const suggestion = (slug, f, v) => entryOf(slug).facets?.[f]?.[v] || '';
function setSuggestion(slug, f, v, d) {
  update(slug, (e) => {
    const fs = ((e.facets ||= {})[f] ||= {});
    if (d) fs[v] = d;
    else delete fs[v];
  });
  edited(slug);
}
function undecidedSuggestions(slug) {
  return Object.entries(piece(slug).proposed).flatMap(([f, vs]) =>
    vs.filter((v) => !suggestion(slug, f, v)).map((v) => `${f}: ${v}`),
  );
}
// The values the piece will carry: its list plus the accepted suggestions.
function shownValues(slug, f) {
  const list = [...facetList(slug, f)];
  for (const v of piece(slug).proposed[f] || [])
    if (suggestion(slug, f, v) === 'accept' && !list.includes(v)) list.push(v);
  return list;
}

const known = (f, v) => (TAXONOMY[f] || []).includes(v);
function labelOf(f, v) {
  if (LABELS[f]?.[v]) return LABELS[f][v];
  for (const e of Object.values(state)) {
    const l = e.labels?.[f]?.[v];
    if (l?.trim()) return l.trim();
  }
  return '';
}
function setLabel(slug, f, v, value) {
  update(slug, (e) => {
    const ls = ((e.labels ||= {})[f] ||= {});
    if (value.trim()) ls[v] = value;
    else delete ls[v];
  });
  edited(slug);
}

function edited(slug) {
  lintSoon(slug);
  renderTop();
  renderQueue();
}

// --- checks ------------------------------------------------------------------------------

const lintTimers = {};
function lintSoon(slug) {
  clearTimeout(lintTimers[slug]);
  lintTimers[slug] = setTimeout(async () => {
    await lint(slug);
    if (cur().slug === slug) renderChecks();
  }, 400);
}
async function lint(slug) {
  try {
    const res = await fetch('lint', {
      method: 'POST',
      body: JSON.stringify({ slug, entry: entryOf(slug) }),
    });
    lints[slug] = await res.json();
  } catch {
    lints[slug] = { errors: [], warnings: [], fresh: ['The checks could not run.'] };
  }
  return lints[slug];
}

// --- the picture ---------------------------------------------------------------------------

const imgUrl = (slug, variant, aspect, theme) =>
  `img/${slug}/${variant}/${aspect.replace(':', 'x')}/${theme}.svg`;

function renderImage() {
  const s = cur();
  const img = $('img');
  const src = imgUrl(s.slug, view.comparing ? 'default' : s.variant, view.aspect, view.theme);
  if (img.getAttribute('src') !== src) {
    $('missing').hidden = true;
    img.hidden = false;
    img.src = src;
  }
  const showing = $('showing');
  showing.hidden = !view.comparing;
  showing.textContent = `Default: ${versionText(s.slug, 'default', 'label') || 'the piece'}`;
  fit();
}

function fit() {
  const stage = $('stage');
  const img = $('img');
  const [w, h] = CANVAS[view.aspect];
  let k;
  if (view.zoom) k = ZOOM_WIDTH / CANVAS['16:9'][0] / devicePixelRatio;
  else {
    const pad = document.fullscreenElement ? 0 : 32;
    k = Math.min((stage.clientWidth - pad) / w, (stage.clientHeight - pad) / h);
  }
  img.style.width = `${Math.floor(w * k)}px`;
  img.style.height = `${Math.floor(h * k)}px`;
  stage.classList.toggle('zoomed', view.zoom);
}

function pan(e) {
  const stage = $('stage');
  const r = stage.getBoundingClientRect();
  stage.scrollLeft = ((e.clientX - r.left) / r.width) * (stage.scrollWidth - stage.clientWidth);
  stage.scrollTop = ((e.clientY - r.top) / r.height) * (stage.scrollHeight - stage.clientHeight);
}

function setZoom(on, e) {
  view.zoom = on;
  fit();
  if (on && e) pan(e);
}

function compare(on) {
  const s = cur();
  if (on && s.variant === 'default') return toast('This is the default version.');
  if (view.comparing === on) return;
  view.comparing = on;
  renderImage();
}

function setAspect(a) {
  view.aspect = a;
  renderShapes();
  renderImage();
  preload();
}
function shape(d) {
  const list = aspectsOf(cur());
  setAspect(list[(list.indexOf(view.aspect) + d + list.length) % list.length]);
}
function theme(d) {
  const names = THEMES.map((t) => t.name);
  view.theme = names[(names.indexOf(view.theme) + d + names.length) % names.length];
  $('theme').value = view.theme;
  renderImage();
  preload();
}
const themeName = (n) => (n[0].toUpperCase() + n.slice(1)).replaceAll('-', ' ');

function toggleFull() {
  if (document.fullscreenElement) document.exitFullscreen();
  else $('stage').requestFullscreen();
}

function preload() {
  const near = [STEPS[view.i + 1], STEPS[nextUndecided(view.i)]].filter(Boolean);
  const urls = near.map((n) => {
    const a = aspectsOf(n).includes(view.aspect) ? view.aspect : '16:9';
    return imgUrl(n.slug, n.variant, a, view.theme);
  });
  const s = cur();
  if (s.variant !== 'default') urls.push(imgUrl(s.slug, 'default', view.aspect, view.theme));
  for (const u of urls) new Image().src = u;
}

// --- rendering -----------------------------------------------------------------------------

function render() {
  renderTop();
  renderShapes();
  renderImage();
  renderSide();
  renderQueue();
}

function renderTop() {
  const s = cur();
  const st = isMoot(s) ? '' : statusOf(s);
  $('title').textContent = text(s.slug, 'title') || s.slug;
  $('version').textContent = hasVersions(s.slug)
    ? versionText(s.slug, s.variant, 'label') || s.variant
    : '';
  const word = wordOf(s, st);
  const badge = $('badge');
  badge.className = `badge ${st}`;
  badge.textContent = isMoot(s) ? 'Piece removed' : word ? `${kindOf(s)} · ${word}` : kindOf(s);
}

function renderShapes() {
  $('shapes').replaceChildren(
    ...aspectsOf(cur()).map((a) =>
      el('button', {
        type: 'button',
        'aria-pressed': String(a === view.aspect),
        text: a,
        onclick: () => setAspect(a),
      }),
    ),
  );
}

function renderSide() {
  const s = cur();
  const parts = [decideSection(s)];
  if (!isMoot(s)) {
    parts.push(wordsSection(s), facetsSection(s), el('section', { class: 'checks', id: 'checks' }));
  }
  parts.push(aboutSection(s));
  $('side').replaceChildren(...parts);
  renderChecks();
}

function decideSection(s) {
  if (isMoot(s)) {
    return el(
      'section',
      { class: 'decide' },
      el('p', {
        class: 'kind',
        text: 'Not asked: the piece is removed. Undo that to decide this one.',
      }),
    );
  }
  const st = statusOf(s);
  const note = el('textarea', {
    id: 'note',
    rows: 2,
    value: decisionOf(s).note || '',
    placeholder: {
      keep: 'Anything to add, like more versions of this? Enter to go on',
      edit: 'What should change? Enter to go on',
      drop: "What's wrong with it?",
    }[st],
  });
  note.oninput = () => setDecision(s, 'note', note.value.trim() ? note.value : '');
  note.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const go_on = noteAdvances;
      note.blur();
      if (go_on) advance();
    } else if (e.key === 'Escape') note.blur();
  };
  note.onblur = () => (noteAdvances = false);
  const button = (cls, label, key, onclick) =>
    el(
      'button',
      { type: 'button', class: cls, 'aria-pressed': String(st === cls), onclick },
      label,
      el('kbd', { text: key }),
    );
  return el(
    'section',
    { class: 'decide' },
    el('p', { class: 'kind', text: kindLine(s) }),
    el(
      'div',
      { class: 'buttons' },
      button('keep', 'Accept', 'A', accept),
      button('edit', 'Edit', 'E', edit),
      button('drop', s.published ? 'Unpublish' : 'Remove', 'R', remove),
    ),
    el(
      'div',
      { class: 'buttons' },
      el(
        'button',
        { type: 'button', disabled: !st, onclick: undo },
        'Undo',
        el('kbd', { text: 'U' }),
      ),
      el('button', { type: 'button', onclick: skip }, 'Skip', el('kbd', { text: 'S' })),
    ),
    el('p', { id: 'flash', class: 'flash', 'aria-live': 'polite' }),
    el('label', { class: 'field' }, { edit: 'What to change', drop: 'Why' }[st] || 'Note', note),
  );
}

function field(label, value, original, rows, onInput, placeholder) {
  const input =
    rows === 1
      ? el('input', { type: 'text', value, placeholder })
      : el('textarea', { rows, value, placeholder });
  const wrap = el('label', { class: `field${value !== original ? ' changed' : ''}` }, label, input);
  input.oninput = () => {
    onInput(input.value);
    wrap.classList.toggle('changed', input.value !== original);
  };
  input.onkeydown = (e) => {
    if (e.key === 'Escape' || (e.key === 'Enter' && rows === 1)) input.blur();
  };
  return wrap;
}

function wordsSection(s) {
  const p = piece(s.slug);
  const sec = el('section', { class: 'words' }, el('h2', { text: 'Text' }));
  for (const [key, label, rows] of TEXT)
    sec.append(field(label, text(s.slug, key), p[key], rows, (v) => setText(s.slug, key, v)));
  if (hasVersions(s.slug)) {
    const v = p.versions[s.variant];
    sec.append(
      el('h2', { text: 'This version' }),
      field('Name', versionText(s.slug, s.variant, 'label'), v.label, 1, (x) =>
        setVersionText(s.slug, s.variant, 'label', x),
      ),
    );
    if (s.variant !== 'default') {
      const desc = versionText(s.slug, s.variant, 'description');
      sec.append(
        field(
          'Description',
          desc,
          v.description,
          3,
          (x) => setVersionText(s.slug, s.variant, 'description', x),
          "Empty: the piece's description is used",
        ),
      );
    }
  }
  return sec;
}

function chip(label, value, onRemove, cls = 'chip') {
  return el(
    'span',
    { class: cls, title: value },
    label,
    el('button', { type: 'button', 'aria-label': `Remove ${label}`, onclick: onRemove }, '✕'),
  );
}

function facetsSection(s) {
  const sec = el('section', { class: 'facets' }, el('h2', { text: 'Facets' }));
  for (const [f, name] of FACETS) sec.append(facetBox(s.slug, f, name));
  return sec;
}

function facetBox(slug, f, name) {
  const chips = el('div', { class: 'chips' });
  const list = facetList(slug, f);
  const again = () => {
    renderSide();
    document.querySelector(`[data-add="${f}"]`)?.focus();
  };
  for (const v of list) {
    const drop_ = () => {
      setFacetList(
        slug,
        f,
        list.filter((x) => x !== v),
      );
      again();
    };
    chips.append(chip(labelOf(f, v) || v, v, drop_));
  }
  for (const v of piece(slug).proposed[f] || []) {
    const d = suggestion(slug, f, v);
    const label = labelOf(f, v) || v;
    const set = (to) => () => {
      setSuggestion(slug, f, v, to);
      again();
    };
    if (d === 'accept') chips.append(chip(label, v, set('decline')));
    else if (d === 'decline')
      chips.append(
        el(
          'span',
          { class: 'chip suggested', title: `${v}, declined` },
          el('s', { text: label }),
          el(
            'button',
            { type: 'button', 'aria-label': `Undo declining ${label}`, onclick: set('') },
            '↺',
          ),
        ),
      );
    else
      chips.append(
        el(
          'span',
          { class: 'chip suggested', title: `${v}, suggested` },
          `${label}?`,
          el(
            'button',
            { type: 'button', 'aria-label': `Accept ${label}`, onclick: set('accept') },
            '✓',
          ),
          el(
            'button',
            { type: 'button', 'aria-label': `Decline ${label}`, onclick: set('decline') },
            '✕',
          ),
        ),
      );
  }
  const box = el('div', { class: 'facet' }, el('h3', { text: name }), chips);
  for (const v of shownValues(slug, f)) {
    if (known(f, v)) continue;
    const own = entryOf(slug).labels?.[f]?.[v];
    const input = el('input', {
      type: 'text',
      value: own ?? labelOf(f, v),
      placeholder: 'What visitors read',
    });
    input.oninput = () => setLabel(slug, f, v, input.value);
    box.append(el('label', { class: 'new-label' }, `New value “${v}”. Visitors read:`, input));
  }
  const add = el('input', { type: 'text', list: `dl-${f}`, placeholder: 'Add…', 'data-add': f });
  const commit = () => {
    const raw = add.value.trim();
    if (!raw) return;
    const byLabel = (TAXONOMY[f] || []).find(
      (v) => (LABELS[f]?.[v] || '').toLowerCase() === raw.toLowerCase(),
    );
    const v =
      byLabel ||
      raw
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
    if (!v) return;
    if (!shownValues(slug, f).includes(v)) setFacetList(slug, f, [...list, v]);
    again();
  };
  add.onkeydown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') add.blur();
  };
  // Picking from the datalist arrives as an input event without a typed character.
  add.oninput = (e) => {
    if (e.inputType === 'insertReplacementText' || e.inputType === undefined) commit();
  };
  box.append(el('div', { class: 'chip-add' }, add));
  return box;
}

function renderChecks() {
  const box = $('checks');
  if (!box) return;
  const r = lints[cur().slug];
  box.replaceChildren(el('h2', { text: 'Checks' }));
  if (!r) return box.append(el('p', { class: 'quiet', text: 'Checking…' }));
  const fresh = r.fresh;
  const old = r.errors.filter((e) => !fresh.includes(e));
  const list = (items, cls) => el('ul', { class: cls }, ...items.map((t) => el('li', { text: t })));
  if (!fresh.length && !old.length && !r.warnings.length)
    return box.append(el('p', { class: 'quiet', text: 'Nothing to fix.' }));
  if (fresh.length)
    box.append(
      el('p', { class: 'blocking', text: 'Apply skips this piece until your edits fix this:' }),
      list(fresh, 'blocking'),
    );
  if (old.length)
    box.append(
      el('p', { class: 'quiet', text: 'Already wrong before your edits:' }),
      list(old, 'quiet'),
    );
  if (r.warnings.length) box.append(list(r.warnings, 'quiet'));
}

function aboutSection(s) {
  const p = piece(s.slug);
  const sec = el(
    'section',
    { class: 'about' },
    el('h2', { text: 'Credits' }),
    el('p', { text: `License: ${p.license}` }),
  );
  for (const src of p.sources) {
    const who = [src.author, src.title || src.topic, src.year].filter(Boolean).join(', ');
    const line = el('p', {}, `${src.kind || 'source'}: ${who} `);
    if (src.url)
      line.append(el('a', { href: src.url, target: '_blank', rel: 'noreferrer', text: 'link' }));
    sec.append(line);
  }
  sec.append(el('p', { text: `wallpapers/${s.slug}` }));
  return sec;
}

function buildQueue() {
  $('squares').replaceChildren(
    ...STEPS.map((s, i) =>
      el('button', {
        type: 'button',
        class: i === 0 || STEPS[i - 1].slug !== s.slug ? 'first' : null,
        onclick: () => go(i),
      }),
    ),
  );
}

function renderQueue() {
  [...$('squares').children].forEach((b, i) => {
    const s = STEPS[i];
    const moot = isMoot(s);
    const st = moot ? '' : statusOf(s);
    for (const k of ['keep', 'edit', 'drop']) b.classList.toggle(k, st === k);
    b.classList.toggle('moot', moot);
    b.classList.toggle('here', i === view.i);
    b.title = `${nameOf(s)} (${kindOf(s).toLowerCase()})`;
    b.setAttribute('aria-label', b.title);
  });
  const decided = STEPS.filter((s) => statusOf(s) || isMoot(s)).length;
  $('count').textContent = `${view.i + 1} of ${STEPS.length} · ${decided} decided`;
  $('squares').children[view.i]?.scrollIntoView({ block: 'nearest' });
}

function flash(msg) {
  const f = $('flash');
  if (f) f.textContent = msg;
}
function toast(msg) {
  $('toast').textContent = msg;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($('toast').textContent = ''), 5000);
}

// --- moving and deciding ---------------------------------------------------------------------

function go(i) {
  view.i = Math.max(0, Math.min(STEPS.length - 1, i));
  view.comparing = false;
  view.zoom = false;
  noteAdvances = false;
  if (!aspectsOf(cur()).includes(view.aspect)) view.aspect = '16:9';
  render();
  const slug = cur().slug;
  if (!lints[slug])
    lint(slug).then(() => {
      if (cur().slug === slug) renderChecks();
    });
  preload();
}

function nextUndecided(from) {
  for (let k = 1; k <= STEPS.length; k++) {
    const j = (from + k) % STEPS.length;
    if (!statusOf(STEPS[j]) && !isMoot(STEPS[j])) return j;
  }
  return -1;
}

function advance() {
  const j = nextUndecided(view.i);
  if (j < 0) {
    render();
    toast('Everything has a decision. Done shows what will be written.');
  } else go(j);
}

// The note field takes the focus, and Enter in it goes on to the next undecided.
function askNote() {
  render();
  noteAdvances = true;
  $('note').focus();
}

function accept() {
  const s = cur();
  if (isMoot(s)) return;
  if (s.variant === 'default' && !s.published) {
    const pending = undecidedSuggestions(s.slug);
    if (pending.length)
      return flash(`Accept or decline the suggested facets first: ${pending.join(', ')}.`);
  }
  setDecision(s, 'status', 'keep');
  if (document.fullscreenElement) return advance();
  askNote();
}

// An edit needs its note, so it leaves fullscreen to show the field.
function edit() {
  const s = cur();
  if (isMoot(s)) return;
  setDecision(s, 'status', 'edit');
  if (document.fullscreenElement) document.exitFullscreen();
  askNote();
}

function remove() {
  const s = cur();
  if (isMoot(s)) return;
  setDecision(s, 'status', 'drop');
  advance();
}

// Leaves the step undecided; the queue comes back to it after the others.
function skip() {
  const j = nextUndecided(view.i);
  if (j < 0 || j === view.i) return toast('Nothing else is undecided.');
  go(j);
}

function undo() {
  setDecision(cur(), 'status', '');
  render();
}

// --- summary and apply -----------------------------------------------------------------------

function changes(slug) {
  const p = piece(slug);
  const rows = [];
  for (const [key, label] of TEXT)
    if (text(slug, key) !== p[key]) rows.push([label, p[key], text(slug, key)]);
  const words = (f, vs) => vs.map((v) => labelOf(f, v) || v).join(', ');
  for (const [f, label] of FACETS) {
    const now = shownValues(slug, f);
    if (!sameList(now, p[f])) rows.push([label, words(f, p[f]), words(f, now)]);
  }
  for (const [name, v] of Object.entries(p.versions)) {
    for (const [key, label] of [
      ['label', 'name'],
      ['description', 'description'],
    ]) {
      if (name === 'default' && key === 'description') continue;
      const now = versionText(slug, name, key);
      if (now !== v[key]) rows.push([`Version “${v.label || name}”, ${label}`, v[key], now]);
    }
  }
  return rows;
}

function newValues() {
  const out = new Map();
  for (const slug of Object.keys(PIECES)) {
    if (!hasEdits(slug)) continue;
    for (const [f] of FACETS)
      for (const v of shownValues(slug, f)) if (!known(f, v)) out.set(`${f}: ${v}`, labelOf(f, v));
  }
  return out;
}

async function openSummary() {
  await flush();
  await Promise.all(Object.keys(PIECES).filter(hasEdits).map(lint));
  renderSummary();
  $('summary').hidden = false;
  $('summary').scrollTop = 0;
}

function renderSummary() {
  const groups = { publish: [], edit: [], drop: [], unpublish: [], undecided: [], noted: [] };
  let checked = 0;
  STEPS.forEach((s, i) => {
    if (isMoot(s)) return;
    const st = statusOf(s);
    if (st === 'edit') groups.edit.push(i);
    else if (!s.published)
      groups[st === 'keep' ? 'publish' : st === 'drop' ? 'drop' : 'undecided'].push(i);
    else if (st === 'drop') groups.unpublish.push(i);
    else if (st === 'keep' && decisionOf(s).note?.trim()) groups.noted.push(i);
    else if (st === 'keep') checked++;
  });
  const problems = [];
  for (const i of groups.publish) {
    const s = STEPS[i];
    const pending = s.variant === 'default' ? undecidedSuggestions(s.slug) : [];
    if (pending.length) problems.push([i, `decide the suggested facets: ${pending.join(', ')}`]);
  }
  for (const slug of Object.keys(PIECES).filter(hasEdits)) {
    const i = STEPS.findIndex((s) => s.slug === slug);
    for (const f of lints[slug]?.fresh || []) problems.push([i, f]);
  }

  const back = (i) => () => {
    closeOverlays();
    go(i);
  };
  const thumb = (s) =>
    el('img', { src: imgUrl(s.slug, s.variant, '16:9', 'fireproof'), loading: 'lazy', alt: '' });
  const row = (i, extra) => {
    const s = STEPS[i];
    const note = decisionOf(s).note?.trim();
    return el(
      'li',
      { onclick: back(i) },
      thumb(s),
      el(
        'div',
        {},
        el('span', { class: 'what', text: nameOf(s) }),
        extra,
        note && el('span', { class: 'why', text: note }),
      ),
    );
  };
  const section = (title, hint, items) =>
    items.length
      ? [
          el(
            'h3',
            {},
            `${title} `,
            el('small', { text: `${items.length}${hint ? ` · ${hint}` : ''}` }),
          ),
          el('ul', { class: 'rows' }, ...items),
        ]
      : [];

  const sheet = el('div', { class: 'sheet' }, el('h2', { text: 'What Apply will write' }));
  sheet.append(
    ...section(
      'Publish',
      '',
      groups.publish.map((i) => row(i)),
    ),
    ...section(
      'Edit',
      'the agent changes these; they stay as they are until the next review',
      groups.edit.map((i) =>
        row(
          i,
          !decisionOf(STEPS[i]).note?.trim() &&
            el('span', {
              class: 'why blocking',
              text: 'No note: the agent will not know what to change.',
            }),
        ),
      ),
    ),
    ...section(
      'Unpublish',
      'hidden from the site; the files stay',
      groups.unpublish.map((i) =>
        row(
          i,
          STEPS[i].variant === 'default' &&
            el('span', { class: 'why', text: 'Hides every version of the piece.' }),
        ),
      ),
    ),
    ...section(
      'Remove',
      'they stay drafts until the agent deletes them, after asking you',
      groups.drop.map((i) => row(i)),
    ),
    ...section(
      'Undecided',
      'they stay drafts',
      groups.undecided.map((i) => row(i)),
    ),
    ...section(
      'Accepted with a note',
      'already on the site; the agent reads the note',
      groups.noted.map((i) => row(i)),
    ),
  );
  if (checked)
    sheet.append(
      el('p', {
        class: 'why',
        text: `${checked} already on the site were checked and stay as they are.`,
      }),
    );

  const edits_ = Object.keys(PIECES)
    .filter(hasEdits)
    .flatMap((slug) =>
      changes(slug).map(([label, before, after]) =>
        el(
          'li',
          { onclick: back(STEPS.findIndex((s) => s.slug === slug)) },
          el(
            'div',
            {},
            el('span', { class: 'what', text: `${text(slug, 'title')}: ${label}` }),
            before && el('span', { class: 'before', text: before }),
            el('span', { text: after || '(empty)' }),
          ),
        ),
      ),
    );
  sheet.append(...section('Text and facet changes', '', edits_));
  const values = [...newValues()].map(([key, label]) =>
    el(
      'li',
      {},
      el('span', {
        class: label ? 'what' : 'what blocking',
        text: `${key}: ${label ? `“${label}”` : 'needs the words visitors see'}`,
      }),
    ),
  );
  sheet.append(...section('New facet values', 'added to taxonomy.yaml', values));
  sheet.append(
    ...section(
      "Can't apply yet",
      'Apply is off until these are fixed',
      problems.map(([i, t]) =>
        el(
          'li',
          { onclick: back(i) },
          el(
            'div',
            {},
            el('span', { class: 'what', text: nameOf(STEPS[i]) }),
            el('span', { class: 'why blocking', text: t }),
          ),
        ),
      ),
    ),
  );
  const apply = el(
    'button',
    { type: 'button', class: 'primary', disabled: problems.length > 0, onclick: applyAll },
    'Apply',
  );
  sheet.append(
    el(
      'div',
      { class: 'actions' },
      el('button', { type: 'button', onclick: closeOverlays }, 'Back to review'),
      apply,
    ),
  );
  $('summary').replaceChildren(sheet);
}

async function applyAll(e) {
  e.target.disabled = true;
  await flush();
  let res;
  try {
    res = await (await fetch('apply', { method: 'POST', body: '{}' })).json();
  } catch (err) {
    res = { error: String(err) };
  }
  renderResult(res);
}

function renderResult(res) {
  const sheet = el(
    'div',
    { class: 'sheet' },
    el('h2', { text: res.error ? 'Nothing was written' : 'Written' }),
  );
  if (res.error) sheet.append(el('p', { class: 'blocking', text: res.error }));
  const version = (v) => (v.variant === 'default' ? v.slug : `${v.slug} (${v.variant})`);
  const lines = [
    ['Published', [...(res.published || []), ...(res.published_variants || []).map(version)]],
    [
      'Sent back for an edit',
      res.error ? [] : (res.edit || []).map((v) => `${version(v)}: ${v.note || 'no note'}`),
    ],
    ['Unpublished', (res.unpublished || []).map(version)],
    ['Changed text and facets', [...new Set((res.edits || []).map((e) => version(e)))]],
    [
      'New facet values',
      (res.new_facets || []).map((f) => `${f.facet}: ${f.value} (“${f.label}”)`),
    ],
    ['Skipped', (res.refused || []).map((r) => `${r.slug}: ${r.reason}`)],
  ];
  for (const [title, items] of lines)
    if (items.length)
      sheet.append(
        el('h3', { text: title }),
        el('ul', {}, ...items.map((t) => el('li', { text: t }))),
      );
  sheet.append(el('p', { text: 'The agent has the full result. You can close this tab.' }));
  $('summary').replaceChildren(sheet);
}

function openHelp() {
  $('help').hidden = false;
}
function closeOverlays() {
  $('summary').hidden = true;
  $('help').hidden = true;
}

// --- wiring --------------------------------------------------------------------------------

function init() {
  const select = $('theme');
  select.replaceChildren(
    ...THEMES.map((t) => el('option', { value: t.name, text: themeName(t.name) })),
  );
  select.value = view.theme;
  select.onchange = () => {
    view.theme = select.value;
    select.blur();
    renderImage();
    preload();
  };
  for (const [f] of FACETS)
    document.body.append(
      el(
        'datalist',
        { id: `dl-${f}` },
        ...(TAXONOMY[f] || []).map((v) => el('option', { value: v, label: LABELS[f]?.[v] || v })),
      ),
    );
  $('finish').onclick = openSummary;
  $('keys').onclick = openHelp;
  $('help').querySelector('[data-close]').onclick = closeOverlays;
  const img = $('img');
  img.onerror = () => {
    img.hidden = true;
    $('missing').hidden = false;
  };
  const stage = $('stage');
  stage.onclick = (e) => setZoom(!view.zoom, e);
  stage.onmousemove = (e) => view.zoom && pan(e);
  window.onresize = fit;
  document.onfullscreenchange = fit;
  window.onblur = () => compare(false);

  document.addEventListener('keydown', (e) => {
    if (!$('summary').hidden || !$('help').hidden) {
      if (e.key === 'Escape') closeOverlays();
      return;
    }
    const t = e.target;
    if (t.matches?.('input, textarea, select') || e.ctrlKey || e.metaKey || e.altKey) return;
    if (t.matches?.('button')) t.blur();
    const actions = {
      ArrowRight: () => go(view.i + 1),
      ArrowLeft: () => go(view.i - 1),
      ArrowUp: () => shape(-1),
      ArrowDown: () => shape(1),
      t: () => theme(1),
      T: () => theme(-1),
      ' ': () => e.repeat || compare(true),
      a: accept,
      e: edit,
      r: remove,
      s: skip,
      u: undo,
      n: () => $('note')?.focus(),
      f: toggleFull,
      '?': openHelp,
      Escape: () => view.zoom && setZoom(false),
    };
    const act = actions[e.key];
    if (!act) return;
    e.preventDefault();
    act();
  });
  document.addEventListener('keyup', (e) => {
    if (e.key === ' ') compare(false);
  });

  buildQueue();
  const first = STEPS.findIndex((s) => !statusOf(s) && !isMoot(s));
  go(first < 0 ? 0 : first);
}

init();

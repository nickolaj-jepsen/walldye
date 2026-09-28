export const meta = {
  name: 'wallpaper-batch',
  description: 'Research, curate, build, prune and review a batch of new walldye wallpapers, landing as draft folders',
  whenToUse: 'The owner wants many new wallpapers (about 10 or more) in one run; for one or a few, use the walldye skill. args: {count, brief?, lenses?, lessons?, licenses?, stop?, cut?, review?}; .claude/workflows/README.md explains each.',
  phases: [
    { title: 'Setup', detail: 'existing names, reference sheets, taxonomy' },
    { title: 'Research', detail: 'one idea agent per lens' },
    { title: 'Curate', detail: 'one art director picks count x 1.25' },
    { title: 'Design', detail: 'per batch of 3: builder, critic, fixer' },
    { title: 'Set', detail: 'build the drafts, near-clones, contact sheets' },
    { title: 'Polish', detail: 'rework and judge the weakest, drop the rest' },
    { title: 'Sources', detail: 'fetch every lead, per group of 3' },
    { title: 'Copy', detail: 'one pass over all new copy' },
    { title: 'Build', detail: 'licences, walldye build, build --verify' },
    { title: 'Review', detail: 'walldye review, then lessons' },
  ],
}

const LENSES = [
  { key: 'plotter-canon', territory: 'Molnar, Nees, Nake, Mohr, LeWitt, Agnes Martin; Tyler Hobbs, inconvergent, Genuary, pen-plotter communities' },
  { key: 'graphic-design', territory: 'Swiss posters, Bauhaus, Constructivism, Japanese kamon and patterns, mid-century, 70s supergraphics, Rams/Aicher, risograph, op-art' },
  { key: 'math-science', territory: 'Chladni, Lissajous, attractors, phyllotaxis, Voronoi, reaction-diffusion, aperiodic tilings, girih, fractals, automata, moire, field lines' },
  { key: 'retro-tech', territory: 'vector displays, oscilloscopes, radar, CRT, punch cards, 1-bit Mac art, demoscene, blueprints, patent drawings, spectrograms, die shots' },
  { key: 'nature-landscape', territory: 'mountains, dunes, swells, aurora, zen gardens, tree rings, strata, eclipses, star trails, rings; national-park posters, woodblocks' },
  { key: 'wallpaper-scene', territory: 'wallhaven, r/unixporn, theme repos and OS defaults: what makes minimal wallpapers work, then fresh compositions' },
  { key: 'wildcard', territory: 'textiles, architecture, maps, music, games, sports markings, sundials, origami creases, stained glass, kintsugi, hanko' },
]

const DEFAULT_BRIEF = `Calm and minimal. The owner loves dithered pieces (vary the dither method from piece to piece), pixel and glyph art, instrument and science displays (radar, helicorder, navball, Smith chart), developer artefacts (schematics, commit graphs, minimaps), crisp patent-style drawings of one contained object, and quiet textures with a small accent event. Avoid big flat accent shapes, clip-art illustration (a lone tree, fireflies, an iceberg), maximalist low-poly landscapes and busy full-sheet blueprints. More in .claude/skills/walldye/references/taste.md and the review lessons at the end of .claude/skills/walldye/references/ideas.md.`

// ---- helpers --------------------------------------------------------------

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
const RESERVED = new Set(['about', 'index', 't', 'og', 'fonts', '404', 'robots', 'favicon'])
const reservedSlug = s => RESERVED.has(s) || s.startsWith('sitemap')
const slugify = s => String(s ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
const chunk = (xs, n) => Array.from({ length: Math.ceil(xs.length / n) }, (_, i) => xs.slice(i * n, i * n + n))
const byKey = (xs, k) => Object.fromEntries((xs ?? []).filter(Boolean).map(x => [x[k], x]))
const uniq = xs => [...new Set(xs)]
const json = x => JSON.stringify(x, null, 1)
const names = (xs, sep = ', ') => xs.map(x => x.name ?? x.slug ?? x).join(sep)

// ---- schemas --------------------------------------------------------------

const str = { type: 'string' }
const strs = { type: 'array', items: str }
const LIGHT = { type: 'string', enum: ['tokens', 'choice', 'branch', 'opt-out'] }
const LEAD = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['recreation', 'inspiration', 'reference', 'data'] },
    title: str,
    author: str,
    year: { type: 'integer' },
    url: str,
  },
  required: ['kind', 'title'],
}
const FACETS = {
  type: 'object',
  properties: { technique: strs, subject: strs, lineage: strs },
  required: ['technique', 'subject', 'lineage'],
}
const IDEA_PROPS = {
  name: { type: 'string', description: 'kebab-case slug, 1-3 words, unique' },
  facets: FACETS,
  concept: { type: 'string', description: '1-2 sentences: what it is, why it is interesting' },
  composition: { type: 'string', description: 'placement on a 1920x1080 canvas, negative space, what is grey and what is accent' },
  method: { type: 'string', description: 'how to generate it procedurally in Python' },
  inspiration: { type: 'string', description: 'artist, movement or phenomenon' },
  leads: { type: 'array', items: LEAD },
}
const IDEA_REQUIRED = ['name', 'facets', 'concept', 'composition', 'method', 'leads']

const SETUP = {
  type: 'object',
  properties: {
    work: { type: 'string', description: 'absolute path of the batch scratch dir' },
    existing: { type: 'array', items: str, description: 'every existing piece slug' },
    references: { type: 'array', items: str, description: 'absolute paths of the family reference sheets' },
    taxonomy: FACETS,
    notes: str,
  },
  required: ['work', 'existing', 'references', 'taxonomy'],
}
const IDEAS = {
  type: 'object',
  properties: {
    sources: strs,
    ideas: { type: 'array', items: { type: 'object', properties: IDEA_PROPS, required: IDEA_REQUIRED } },
  },
  required: ['ideas'],
}
const CURATED = {
  type: 'object',
  properties: {
    selected: {
      type: 'array',
      items: {
        type: 'object',
        properties: { ...IDEA_PROPS, why: { type: 'string', description: 'how it differs from its nearest neighbour' } },
        required: [...IDEA_REQUIRED, 'why'],
      },
    },
    rejected_notes: str,
  },
  required: ['selected', 'rejected_notes'],
}
const BUILT = {
  type: 'object',
  properties: {
    designs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: str,
          status: { type: 'string', enum: ['done', 'failed'] },
          size_kb: { type: 'number' },
          meta_ok: { type: 'boolean' },
          light: LIGHT,
          aspects: strs,
          variants: { ...strs, description: 'names of the draft variants proposed; usually none' },
          notes: str,
        },
        required: ['name', 'status', 'meta_ok', 'light', 'aspects', 'variants', 'notes'],
      },
    },
  },
  required: ['designs'],
}
const CRITIQUE = {
  type: 'object',
  properties: {
    reviews: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: str,
          score: { type: 'integer', minimum: 1, maximum: 10 },
          verdict: { type: 'string', enum: ['keep', 'fix', 'rework'] },
          fixes: strs,
          light_verdict: { type: 'string', enum: ['ok', 'fix'] },
          copy_fixes: strs,
          variants: {
            type: 'array',
            description: 'one verdict per proposed variant; empty when there are none',
            items: {
              type: 'object',
              properties: { name: str, keep: { type: 'boolean' }, reason: str },
              required: ['name', 'keep', 'reason'],
            },
          },
        },
        required: ['name', 'score', 'verdict', 'fixes', 'light_verdict', 'copy_fixes', 'variants'],
      },
    },
  },
  required: ['reviews'],
}
const FIXED = {
  type: 'object',
  properties: {
    designs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: str,
          status: { type: 'string', enum: ['kept', 'improved', 'dropped'] },
          light: LIGHT,
          aspects: strs,
          variants: strs,
          notes: str,
        },
        required: ['name', 'status', 'notes'],
      },
    },
  },
  required: ['designs'],
}
const SET = {
  type: 'object',
  properties: {
    built: strs,
    build_failed: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, error: str }, required: ['slug', 'error'] },
    },
    near_clones: {
      type: 'array',
      items: { type: 'object', properties: { a: str, b: str, similarity: { type: 'number' } }, required: ['a', 'b', 'similarity'] },
    },
    duplicates: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, of: str, reason: str }, required: ['slug', 'of', 'reason'] },
    },
    polish: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, issue: str }, required: ['slug', 'issue'] },
    },
    notes: str,
  },
  required: ['built', 'build_failed', 'near_clones', 'duplicates', 'polish'],
}
const REWORK = {
  type: 'object',
  properties: { summary: str, check_ok: { type: 'boolean' } },
  required: ['summary', 'check_ok'],
}
const JUDGE = {
  type: 'object',
  properties: {
    score: { type: 'integer', minimum: 1, maximum: 10 },
    keep: { type: 'boolean' },
    check_ok: { type: 'boolean' },
    reason: str,
  },
  required: ['score', 'keep', 'check_ok', 'reason'],
}
const DROPPED = {
  type: 'object',
  properties: { dropped: strs, missing: strs, output: str },
  required: ['dropped', 'missing'],
}
const SOURCED = {
  type: 'object',
  properties: {
    designs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          slug: str,
          sources: { type: 'array', items: LEAD },
          dropped: {
            type: 'array',
            items: { type: 'object', properties: { title: str, url: str, reason: str }, required: ['title', 'reason'] },
          },
        },
        required: ['slug', 'sources', 'dropped'],
      },
    },
  },
  required: ['designs'],
}
const COPY = {
  type: 'object',
  properties: {
    changes: {
      type: 'array',
      items: {
        type: 'object',
        properties: { slug: str, field: str, before: str, after: str },
        required: ['slug', 'field', 'after'],
      },
    },
    notes: str,
  },
  required: ['changes'],
}
const FINAL = {
  type: 'object',
  properties: {
    licensed: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, license: str }, required: ['slug', 'license'] },
    },
    built: strs,
    failed: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, error: str }, required: ['slug', 'error'] },
    },
    verify_ok: { type: 'boolean' },
    drift: strs,
    output: str,
  },
  required: ['licensed', 'built', 'failed', 'verify_ok', 'drift'],
}
const REVIEWED = {
  type: 'object',
  properties: {
    url: str,
    finished: { type: 'boolean' },
    approved: strs,
    rejected: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, note: str }, required: ['slug'] },
    },
    undecided: strs,
    notes: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, note: str }, required: ['slug', 'note'] },
    },
    published: strs,
    refused: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, reason: str }, required: ['slug', 'reason'] },
    },
    error: str,
  },
  required: ['finished', 'approved', 'rejected', 'undecided'],
}
const LESSONS_OUT = { type: 'object', properties: { lessons: str }, required: ['lessons'] }

// ---- args -----------------------------------------------------------------

const A = typeof args === 'number' ? { count: args } : (args ?? {})
const COUNT = Number(A.count)
if (!Number.isInteger(COUNT) || COUNT < 1) {
  throw new Error('wallpaper-batch: args.count must be the number of finished wallpapers wanted')
}
const TARGET = Math.ceil(COUNT * 1.25)
// "each technique facet at 10%", but never zero on a small batch.
const CAP = Math.max(1, Math.floor(TARGET / 10))
const BRIEF = String(A.brief || DEFAULT_BRIEF).trim()
const LESSONS = A.lessons ? `\nLESSONS FROM EARLIER REVIEWS (what the owner approved and rejected, and why):\n${String(A.lessons).trim()}\n` : ''
const LICENSES = A.licenses && typeof A.licenses === 'object' ? A.licenses : {}
const CUT = new Set([].concat(A.cut ?? []).map(slugify))
const askedLenses = [].concat(A.lenses ?? []).filter(Boolean)
const LENS_LIST = (askedLenses.length ? askedLenses : LENSES).map((l, i) => {
  if (typeof l === 'string') return LENSES.find(d => d.key === l) ?? { key: `lens-${i + 1}`, territory: l }
  return { key: slugify(l.key) || `lens-${i + 1}`, territory: l.territory ?? String(l.key) }
})
// Fixed so the log can show the review URL before the blocking agent starts.
const REVIEW_PORT = 8742
const PER_LENS = Math.min(28, Math.max(6, Math.ceil((TARGET * 1.6) / LENS_LIST.length)))

// ---- shared prompt blocks -------------------------------------------------

let WORK = ''
let REFS = ''
let TAXONOMY = ''

const TIMING = 'A check or build takes from a few seconds to about half a minute per piece; a dense aspects="any" piece with variants, or a heavy simulation, is the slow end. Over several pieces they run in parallel across the cores.'
const waitFor = pattern => `wait without ending your turn: repeat \`pgrep -f '${pattern}' >/dev/null && timeout 580 tail --pid=$(pgrep -of '${pattern}') -f /dev/null; pgrep -f '${pattern}' >/dev/null && echo running || echo finished\` with a 600000 ms Bash timeout until it prints finished`
const buildJobs = (slugs, tag) => `A Bash call stops after 10 minutes, so start one build over all of them with Bash run_in_background:
   \`uv run walldye build ${slugs.join(' ')} > ${WORK}/${tag}.log 2>&1\`
   Then ${waitFor('[w]alldye build')}. A piece that fails prints "<slug>: not written" after its error lines and writes nothing; the others still build. \`grep -B30 ': not written' ${WORK}/${tag}.log\` shows the failures.`

const LOOK = `THE FAMILY LOOK (non-negotiable):
- Every piece works under any three seed colours (bg, fg, accent). Colours come only from walldye tokens (BG, BG_DEEP, BG_ALT, UI, UI_ALT, UI_HI; MUTED rarely; ACCENT, ACCENT_HI, ACCENT_1..8) and mix(), ladder() and by_regime() of them; a hex value is never a paint. Structure in quiet greys, ONE accent family, no other hues. Pieces are judged under fireproof (the template), flexoki-light and nord.
- The owner's brief, in their words: ${BRIEF}
- Lots of negative space. One focal element (vary placement) OR a quiet full-bleed grey texture with one small accent event. The accent is the event: limited area, never a big flat saturated mass.
- It sits behind windows: greys low-contrast against BG, nothing loud everywhere.
- Pure vector: shapes, paths, gradients, clips, masks, patterns. No text elements, raster images or filters (the API cannot write them). Bitmap-font glyphs via walldye.pixel.glyphs() are fine.
- Crisp at 4K, where the short side is 1080 units: visible strokes at least about 1.2 units; pixel and dither cells an integer 2-8 units on a grid with a whole-unit origin. One <path> per colour where shapes repeat: check warns above 600 kB or 15k elements and fails above 1 MB or 20k.
- Composed like a poster: deliberate placement, nothing awkwardly clipped.
${LESSONS}`

const tool = () => `TOOLING (you are in the walldye repo; run every command from its root):
- Read .claude/skills/walldye/SKILL.md, then .claude/skills/walldye/references/api.md (the design API: colours, canvas, drawing, random streams, params and variants, the geom, field and pixel helpers) and the nearest example in .claude/skills/walldye/examples/. references/principles.md in the same folder has the critique checklist, and references/themes.md the tokens.
- A piece is wallpapers/<slug>/: design.py (a one-line docstring, module-level constants and pure helpers, and one \`@design(...) def draw(s: Canvas) -> None\`; the canvas is s.w by s.h, short side 1080) and meta.yaml. It imports walldye, walldye.geom, walldye.field and walldye.pixel, numpy, scipy, shapely, skimage and the pure standard library (math, itertools and the like); not random, numpy.random or local modules.
- Declare \`@design(aspects="any")\` when the layout follows s.w and s.h (place with s.pick, s.frac and s.inset; sizes in plain units). Without it the piece is 16:9 only and other screens get a crop of it.
- Preview: \`uv run walldye preview <slug>\` prints lint lines, the regime, whether light geometry differs, and the PNG path last. Read the PNG every round. Flags: --crop X,Y,W,H (canvas units) to zoom, --theme flexoki-light, --theme nord, --aspect 32:9 / 9:19.5 / 10:16, --width 480 to judge it at thumbnail size.
- \`uv run walldye check <slug>\` must end with "1/1 ok" (the design lint, ruff, Pyrefly, determinism, recolour fit, every variant). \`uv run ruff format wallpapers/<slug>\` fixes formatting. ${TIMING} Give it a 600000 ms Bash timeout.
- Randomness only from s.rng(key), s.np_rng(key) and s.noise(key); nothing at module level changes while drawing.
- Geometry: colours are symbolic formulas, so key buckets, dicts and sorts by role or index (s.buckets, a ladder and TONES.rung(v)), never by colour; \`s.light\` is the only theme-dependent control flow; mask content is MASK_WHITE, MASK_BLACK and mixes of the two.
- Look at ${REFS} before designing, and match the restraint and finish you see there.
- Files: create or edit only wallpapers/<your slugs>/ (design.py, meta.yaml). Never touch walldye/, taxonomy.yaml, other wallpapers, wallpapers/index.json or any build/ folder. Never run \`walldye build\`, \`drop\` or \`review\`, and always name your own slugs in preview, check and render. Previews land in $WALLDYE_PREVIEW; leave it alone. No git commands that change state.`

const LADDER = `LIGHT LADDER. Under light themes greys walk from BG towards FG, BG_DEEP is lighter than BG, and the dark accent steps turn into pale tints. Climb only as far as needed:
1. tokens only (one template serves both regimes);
2. a per-regime colour, e.g. STRUCT = by_regime(UI, MUTED), dark first (still one template);
3. a geometry branch under \`if s.light:\` (costs a light template per native aspect and variant);
4. \`themes: [dark]\` in meta.yaml, only after 2 and 3 were tried, with the reason in \`notes\`. Under light themes the site then shows the piece with bg and fg swapped.`

const VARIANTS = `VARIANTS (usually none). A variant is a named version of a piece that a visitor can switch to on its page, built for every aspect and regime. Propose one only where the piece has a natural one:
- It must change what is depicted (a moon phase, a rule number, a reaction regime, the moment of a sweep), not nudge a value. A new seed counts only when the result shows something different; seed ladders are for \`walldye sheet <slug> --seeds 0..7\`, not for the site.
- At most 3 per piece, as instances of the piece's Params class in \`@design(variants={...})\`, with draw annotated \`def draw(s: Canvas[ThatClass]) -> None\`. Try values first with \`--set k=v\` or \`walldye sheet <slug> --wedge k=a..b..step\`.
- Each goes under \`variants:\` in meta.yaml with a label (one to four plain words naming what that version shows) and \`draft: true\`; \`default\` gets a label too. An optional description replaces the piece's when that version is shown. The owner approves each variant in review.
- Preview each with \`--variant <name>\`. \`walldye check <slug>\` checks every variant and fails two versions that look alike at thumbnail size (ink-map cosine 0.93 or more): a detail-only change next to a large fixed structure fails it. Passing is necessary, not sufficient: on a fine-textured piece a 4% nudge of one value can measure 0.91, so a variant that passes check can still be a nudge.`

const COPY_RULES = `COPY RULES (the site publishes title, description, notes and the design.py docstring):
- title: a few plain words a visitor would use. A variant label follows the same rules.
- description: one or two short sentences, at most 30 words, concrete about what is drawn and how.
- Theme-neutral: no colour names, and no theme roles as nouns ("the accent"); say what is picked out, filled in or lit.
- No evaluative adjectives (stunning, mesmerising, elegant, timeless).
- Nothing about how the site works inside: no internal terms (regime, seed, token, native, hand-tuned, light-ready, preset, variant, param, slot, template, derived; visitors see variants as versions), no licence names or identifiers (CC0, SPDX, LicenseRef-...), no contrast ratios, colour tolerances or pixel sizes, no keyboard hints.
- Italics only for titles of works (*Schotter* in notes). Source titles stay plain text; the site italicises them. Vary the sentence shape; don't open with "A ..." every time.
- The docstring is one theme-neutral line: concept plus technique. Comments name tokens or roles, never hues.`

// A function because TAXONOMY is only known after setup.
const metaRules = () => `META.YAML (written by \`walldye new\`; keep draft, author, model and added as it wrote them):
- title and description follow the COPY RULES below.
- technique, subject, lineage: values from taxonomy.yaml only (${TAXONOMY}). A missing value goes under proposed_facets as {facet: [value]}; never edit taxonomy.yaml.
- themes: [dark] and notes only at ladder step 4. Otherwise notes (optional Markdown) is for anything a visitor would want to know.
- Leave sources: [] and add no license line. A later agent verifies the leads and writes the sources.
${COPY_RULES}`

const spec = ideas => json(ideas.map(i => ({
  name: i.name,
  facets: i.facets,
  concept: i.concept,
  composition: i.composition,
  method: i.method,
  inspiration: i.inspiration,
  leads: i.leads,
})))

const needsFix = r => !r || r.verdict !== 'keep' || r.fixes.length > 0 || r.copy_fixes.length > 0 || r.light_verdict !== 'ok' || r.variants.some(v => !v.keep)

// ---- 0. setup -------------------------------------------------------------

phase('Setup')
const setup = await agent(`Prepare shared context for a batch of new wallpapers. You are in the walldye repo; change nothing in it.

1. Scratch dir: \`uv run python -c "from walldye.tools.preview import preview_dir; print(preview_dir())"\` prints the preview dir. Create <that dir>/batch; it is WORK. Return its absolute path as work.
2. Existing names. \`uv run walldye list\` prints one line per piece: slug, title, description, draft, aspects and named variants, tab-separated. Write WORK/existing.txt with one line per piece, "slug: description", and return every slug as existing.
3. Reference sheets. Pick about 30 pieces that match .claude/skills/walldye/references/taste.md (dither, pixel, glyph, instrument and technical-drawing pieces; skip the fan pieces, whose meta.yaml sets \`license: LicenseRef-fan-work\`) and sheet them as the family: \`uv run walldye sheet <slugs> --cols 6 -o WORK/reference.png\`. Then sheet the whole catalogue small, for spotting look-alikes: \`uv run walldye sheet --all --cols 12 --thumb 160 -o WORK/catalogue.png\`. Read both PNGs to confirm they rendered. Return the path of reference.png as references.
4. Read taxonomy.yaml and return its technique, subject and lineage values as taxonomy.`, { label: 'setup', phase: 'Setup', schema: SETUP })

if (!setup) throw new Error('wallpaper-batch: the setup agent returned nothing, and the existing-name list is needed to avoid slug collisions')
WORK = setup.work.replace(/\/+$/, '')
REFS = setup.references.length ? setup.references.join(' and ') : `${WORK}/reference.png`
TAXONOMY = `technique: ${setup.taxonomy.technique.join(', ')}; subject: ${setup.taxonomy.subject.join(', ')}; lineage: ${setup.taxonomy.lineage.join(', ')}`
const existing = new Set(setup.existing.map(slugify))
log(`${existing.size} existing names; scratch dir ${WORK}`)

// ---- 1. research ----------------------------------------------------------

phase('Research')
const pools = await parallel(LENS_LIST.map(l => () => agent(`${LOOK}
EXISTING DESIGNS (do not duplicate; a riff is fine only if clearly distinct): Read ${WORK}/existing.txt and look at ${WORK}/catalogue.png, a sheet of every piece. Look at ${REFS}: that is the family.

YOUR LENS: ${l.territory}

1. Research first: roughly 8-15 web searches or fetches surveying your lens for specific works, visual ideas and techniques (load WebSearch and WebFetch with ToolSearch if they are deferred). Concrete references beat generic ones.
2. Brainstorm ${PER_LENS} concepts that fit THE FAMILY LOOK. Range matters: vary scale (tiny focal object vs full-bleed texture), placement, density and technique. No clusters of variants of one idea.
3. Give each a concrete composition (placement on a 1920x1080 canvas, what is grey and what is accent) and a concrete Python-to-SVG method.
4. facets: technique, subject and lineage values from taxonomy.yaml (${TAXONOMY}). When nothing fits, use a new lowercase slug; it becomes a proposal for the owner.
5. leads: the specific works, papers, datasets or pages behind the idea, as {kind, title, author, year, url}. kind is recreation (the piece would redraw that specific work), inspiration, reference (a technique or phenomenon) or data (a dataset it plots). Give a url only when you found one. A later agent fetches every lead and drops the ones that don't check out, so never invent one.
Names: kebab-case slugs of 1-3 words, unique, not in existing.txt, not about/index/t/og/fonts/404/robots/favicon, not starting with "sitemap".`,
  { label: `lens:${l.key}`, phase: 'Research', schema: IDEAS })))

const pool = pools.flatMap((r, i) => (r?.ideas ?? []).map(idea => ({ ...idea, lens: LENS_LIST[i].key })))
const deadLenses = LENS_LIST.filter((_, i) => !pools[i]).map(l => l.key)
if (deadLenses.length) log(`No ideas from lens ${deadLenses.join(', ')} (agent failed)`)
if (!pool.length) throw new Error('wallpaper-batch: no lens agent returned ideas')
log(`${pool.length} ideas from ${LENS_LIST.length - deadLenses.length} lenses`)

// ---- 2. curate ------------------------------------------------------------

phase('Curate')
const curated = await agent(`${LOOK}
You are the art director curating a wallpaper set. Below are ${pool.length} brainstormed ideas (JSON) from ${LENS_LIST.length} research lenses. Select exactly ${TARGET} for production (the owner wants ${COUNT}; attrition later is real). Select fewer only if the pool cannot supply ${TARGET} that pass these rules, and say why in rejected_notes.
- No near-duplicates: merge ideas that would look alike (same motif and method), keeping the stronger spec and combining the best details and leads.
- Nothing that duplicates an EXISTING design at thumbnail size: Read ${WORK}/existing.txt and look at ${WORK}/catalogue.png. Names must not collide with any name in existing.txt.
- Diversity: at most ${CAP} of the selected ideas may share any one technique facet value (10% of ${TARGET}, and at least one); an idea with two technique values counts towards both. Mix roughly 55% focal-object compositions, 30% quiet full-bleed textures with an accent event and 15% bold graphic or poster pieces. Vary focal placement (not everything right of centre).
- Reject anything off-look: other hues, photos, filters, loud or busy behind windows.
- Feasibility: buildable in Python to a template under 600 kB. Rewrite vague methods concretely.
- Tighten each composition so a designer can build it without guessing: positions, rough sizes, which elements are accent and which grey.
- Keep facets on taxonomy values where one fits (${TAXONOMY}). Carry the leads over; don't invent new ones.
IDEAS:
${json(pool)}`, { label: 'curate', phase: 'Curate', schema: CURATED })

if (!curated) throw new Error('wallpaper-batch: the curator returned nothing')
const ideas = []
const curateNotes = []
const perTechnique = {}
for (const raw of curated.selected) {
  if (ideas.length === TARGET) {
    curateNotes.push(`${raw.name}: past the ${TARGET} asked for`)
    continue
  }
  const name = slugify(raw.name)
  let problem = null
  if (!SLUG.test(name) || reservedSlug(name)) problem = 'not a usable slug'
  else if (existing.has(name)) problem = 'collides with an existing name'
  else if (ideas.some(i => i.name === name)) problem = 'picked twice'
  else if (CUT.has(name)) problem = 'cut by the owner'
  const techniques = uniq((raw.facets?.technique ?? []).map(slugify).filter(Boolean))
  const full = techniques.filter(t => (perTechnique[t] ?? 0) >= CAP)
  if (!problem && full.length) problem = `over the ${CAP}-piece cap for ${full.join(', ')}`
  if (problem) {
    curateNotes.push(`${raw.name}: ${problem}`)
    continue
  }
  techniques.forEach(t => { perTechnique[t] = (perTechnique[t] ?? 0) + 1 })
  ideas.push({ ...raw, name, facets: { ...raw.facets, technique: techniques } })
}
const unknownCuts = [...CUT].filter(c => !curated.selected.some(s => slugify(s.name) === c))
if (unknownCuts.length) log(`args.cut names not in the curated list: ${unknownCuts.join(', ')}`)
if (curateNotes.length) log(`Left out after curation: ${curateNotes.join('; ')}`)
if (!ideas.length) throw new Error('wallpaper-batch: no curated idea survived the name and cap checks')
log(`${ideas.length} ideas selected (asked for ${TARGET})`)

if (A.stop === 'ideas') {
  return {
    status: 'ideas',
    work: WORK,
    count: COUNT,
    ideas: ideas.map(i => ({ name: i.name, concept: i.concept, composition: i.composition, facets: i.facets, leads: i.leads.map(l => l.title) })),
    left_out: curateNotes,
    rejected_notes: curated.rejected_notes,
    next: [
      'Show the owner these ideas (name and concept).',
      'To build them, relaunch this workflow with resumeFromRunId and the same args minus `stop`, plus `cut: [names]` for ideas to skip. Setup, research and curation come back from the cache.',
    ],
  }
}

// ---- 3. design: builder -> critic -> fixer per batch of 3 -----------------

phase('Design')
const batches = chunk(ideas, 3)
log(`Building ${ideas.length} designs in ${batches.length} batches of up to 3`)

const designed = await pipeline(
  batches,
  (_, batch) => agent(`You are a generative-art designer producing desktop wallpapers for a family the owner loves.
${LOOK}
${tool()}

${LADDER}

${VARIANTS}

${metaRules()}

YOUR DESIGNS: ${names(batch)}. Their specs are at the end.
For each design:
1. \`uv run walldye new <slug> --author "<your model's display name, e.g. Claude Opus 5.5>" --model <your model id, e.g. claude-opus-5-5, without a context suffix such as [1m]>\`. If it says the folder already exists, the folder is yours from an interrupted run of this batch: continue from it.
2. Implement the spec in design.py, starting from the nearest example, and decide the aspects. The spec is a starting point, not a cage: if something reads poorly at wallpaper scale, change it in the spirit of the concept.
3. Preview, Read, critique honestly (composition, balance, density, tone steps, legibility of the idea, restraint), revise. At least 3 rounds, with a --crop into the busiest region, --aspect 32:9, 9:19.5 and 10:16 when aspects are declared, and from round 2 on --theme flexoki-light and --theme nord. End with a full fireproof preview.
4. Climb the light ladder until the flexoki-light render holds up.
5. Propose draft variants only where VARIANTS says the piece has a natural one.
6. Fill meta.yaml as META.YAML says.
7. \`uv run walldye check <slug>\` must end with "1/1 ok".
Return one entry per design: status done or failed; size_kb of the 16:9 render if you measured it; light = the ladder step you ended on (tokens, choice, branch, opt-out); aspects = ["any"] or the aspects tuple in @design, as a list ([] for 16:9 only); variants = the names of the draft variants you proposed ([] for none); meta_ok = meta.yaml filled as META.YAML says and check reports no meta.yaml errors; notes = what you built, key decisions, anything the critic should know.

SPECS:
${spec(batch)}`, { label: `design:${names(batch, ',')}`, phase: 'Design', schema: BUILT }),

  async (built, batch) => {
    const b = byKey(built?.designs, 'name')
    const done = batch.filter(s => b[s.name]?.status === 'done')
    if (!done.length) return { built: b, done, reviews: null }
    const critique = await agent(`You are a demanding art director reviewing new wallpapers for a curated set. Do NOT edit any files.
${LOOK}
${LADDER}

${VARIANTS}

${metaRules()}

Look at ${REFS} first. For each design (${names(done)}):
- \`uv run walldye preview <slug>\` (fireproof, the template), then with --theme flexoki-light and --theme nord. Read every PNG.
- One --crop X,Y,W,H into its busiest region, and --width 480 for the thumbnail read.
- If design.py declares aspects, also --aspect 32:9 and --aspect 9:19.5.
- For each variant in \`@design(variants=...)\`, a preview with --variant <name>.
- If meta.yaml says themes: [dark], the site shows the piece under light themes with bg and fg swapped, so preview it with --theme 100f0f-fffcf0-bc5215 (flexoki-light swapped) instead of flexoki-light, and check that notes gives a real reason.
- Read design.py and meta.yaml.
Judge: does it read instantly; is the composition deliberate; is the accent a restrained event; are the greys quiet enough behind windows; is it clean at 4K (no artefacts, jaggies, awkward clipping, muddy tone steps); does it feel like a sibling of the reference set? Faint is the common failure, more than loud: call it out when the idea only shows up zoomed in.
Light: does the flexoki-light render hold up (tone steps visible, the event still reads, no shadow that turned into a glare) and does the event survive nord's cool accent by shape and size? Is the ladder step the lowest that works, and was an opt-out earned? light_verdict is ok or fix; put light fixes in fixes, prefixed "light:".
Variants: judge each proposed variant against VARIANTS. Does it change what is depicted, is it as strong as the default, and does it look different at thumbnail size? A variant that passes check can still be a nudge of one value: drop it if the subject did not change. Return one verdict per variant in variants (keep false with the reason drops it); [] when the design has none.
Copy: check title, description, notes, variant labels and descriptions, and the docstring against the COPY RULES. Each copy_fixes entry quotes the replacement text.
Score 1-10 for "would it sit proudly in the set as a daily wallpaper". verdict keep only for 8+ with no meaningful fixes; fix for fixable issues; rework if the approach fails. Fixes must be concrete (positions, sizes, tones, density), most important first.
Builder notes: ${json(done.map(s => b[s.name]))}
SPECS:
${spec(done)}`, { label: `critic:${names(done, ',')}`, phase: 'Design', schema: CRITIQUE })
    return { built: b, done, reviews: critique ? byKey(critique.reviews, 'name') : null }
  },

  async (st, batch) => {
    const todo = st.done.filter(s => !st.reviews || needsFix(st.reviews[s.name]))
    if (!todo.length) return { ...st, fixed: null }
    const reviews = todo.map(s => st.reviews?.[s.name] ?? { name: s.name, missing: 'no review: self-review it against the family look and polish' })
    const fixed = await agent(`You are the designer who owns these wallpapers. An art director reviewed them.
${LOOK}
${tool()}

${LADDER}

${VARIANTS}

${metaRules()}

REVIEWS:
${json(reviews)}
For each design above: apply the fixes, the light fixes and the copy_fixes (for rework, rethink the approach but keep the concept), and remove every variant whose verdict has keep false from design.py and meta.yaml. Then preview, Read and revise for at least 2 rounds, including --theme flexoki-light and --theme nord, ending with a passing \`uv run walldye check <slug>\`.
If after a real rework it would still score below 7, delete its folder (\`rm -r wallpapers/<slug>\`) and report it dropped.
Return one entry per design: status kept, improved or dropped; light, aspects and variants as they now stand; notes on what changed.
SPECS:
${spec(todo)}`, { label: `fix:${names(todo, ',')}`, phase: 'Design', schema: FIXED })
    if (!fixed) log(`Fixer for ${names(todo)} returned nothing; keeping the builds as they are, the set pass checks them`)
    return { ...st, fixed: fixed ? byKey(fixed.designs, 'name') : null }
  },
)

const pieces = {}
const dropped = []
batches.forEach((batch, i) => {
  const st = designed[i]
  for (const s of batch) {
    const b = st?.built?.[s.name]
    const f = st?.fixed?.[s.name]
    const r = st?.reviews?.[s.name]
    if (b?.status !== 'done') {
      dropped.push({ slug: s.name, stage: 'design', reason: b?.notes || 'the builder returned nothing for it' })
    } else if (f?.status === 'dropped') {
      dropped.push({ slug: s.name, stage: 'fix', reason: f.notes })
    } else {
      pieces[s.name] = {
        slug: s.name,
        idea: s,
        score: r?.score ?? null,
        light: f?.light ?? b.light,
        aspects: f?.aspects ?? b.aspects,
        variants: f?.variants ?? b.variants,
        notes: f?.notes ?? b.notes,
      }
    }
  }
})
const kept = Object.keys(pieces)
log(`${kept.length} of ${ideas.length} designs kept after critique; ${dropped.length} failed or dropped`)

// ---- 4. set-level pass ----------------------------------------------------

async function dropFolders(slugs) {
  const res = await agent(`Delete the folders of wallpapers that this batch created and then rejected. The owner has never seen them (they were made and turned down within this run), which is why skipping the confirmation prompt is fine here.
Slugs: ${slugs.join(' ')}
1. Keep only the slugs whose wallpapers/<slug>/ folder exists (\`ls -d\`).
2. \`uv run walldye drop <those slugs> --yes\`. It removes the folders, regenerates wallpapers/index.json and clears their review state.
Touch nothing else. Return dropped (removed), missing (no folder) and the command output.`, { label: 'drop', phase: 'Polish', schema: DROPPED, effort: 'low' })
  if (!res) log(`The drop agent returned nothing; these folders may still exist and would fail \`walldye build --verify\`: ${slugs.join(', ')}`)
  return res
}

const cleanupAndReturn = async (status, extra) => {
  const leftovers = uniq(dropped.map(d => d.slug))
  const res = leftovers.length ? await dropFolders(leftovers) : null
  return { status, work: WORK, dropped, cleanup: res, ...extra }
}

if (!kept.length) {
  return await cleanupAndReturn('nothing-kept', { next: ['No design survived critique. Read `dropped` for why, adjust the brief or lessons, and run again.'] })
}

phase('Set')
const scored = kept.map(s => ({ slug: s, score: pieces[s].score, light: pieces[s].light, notes: pieces[s].notes }))
const setRes = await agent(`You run the set-level pass over a batch of new wallpapers. The per-design critics never saw the set; you do.
${LOOK}
NEW PIECES (slug, critic score, light ladder step, designer notes):
${json(scored)}

You may run \`walldye build\` (the designers could not). ${TIMING}
1. Build every new piece. ${buildJobs(kept, 'set')} Note each slug that fails, with its error lines. Do not fix designs yourself.
2. Near-clones: \`uv run python -c "from walldye.tools.check import near_clones; near_clones('${kept.join(' ')}'.split())"\`. This is the near-clone pass of \`walldye check --similar\` without the full check that build just ran. It compares each new piece's build/16x9.svg (the default version) with every built piece and prints \`similar (0.95): a ~ b\` per close pair (nothing when there are none), then \`similar: skipped, no build/16x9.svg: ...\` for the pieces that failed to build. It compares ink maps, so it misses motif-level duplicates (two different mountain pieces); trust your eyes over it, both ways.
3. Contact sheets in pages of 30: \`uv run walldye sheet <slugs> --cols 6 -o ${WORK}/set-<page>.png\`, and each page again with \`--theme flexoki-light -o ${WORK}/set-<page>-light.png\`. Read every page next to ${REFS} and ${WORK}/catalogue.png. Hunt for look-alikes (within the batch and against existing pieces), weak thumbnails, tone that drifts from the family, too many focal points in the same spot, and light renders that fall apart.
4. Decide:
   - duplicates: new pieces to drop because another piece, new or existing, already does the same thing better. Name the one each duplicates. Never list an existing piece, and never both halves of a pair.
   - polish: the weakest ~10%: critic scores of 6 or less, anything the sheets exposed, and every piece that failed to build. One specific issue each, naming the symptom and the target: "Too faint; the lobes do not read. Increase dot size and tone, pick an orbital with a striking silhouette, densest cores in accent" beats "make it better".
Don't edit designs or drop anything; the orchestrator acts on your lists. Return built, build_failed, near_clones, duplicates, polish and notes.`, { label: 'set', phase: 'Set', schema: SET })

if (!setRes) log('The set agent returned nothing: no near-clone pass or polish list this run. The final build still checks every piece.')
const keptSet = new Set(kept)
const gone = new Set(ideas.map(i => i.name).filter(s => !keptSet.has(s)))
const dupes = []
for (const d of setRes?.duplicates ?? []) {
  const lost = gone.has(d.of) || dupes.some(x => x.slug === d.slug || x.slug === d.of)
  if (!keptSet.has(d.slug) || d.slug === d.of || lost) {
    log(`Ignored duplicate entry ${d.slug} ~ ${d.of}`)
    continue
  }
  dupes.push(d)
  dropped.push({ slug: d.slug, stage: 'set', reason: `duplicates ${d.of}: ${d.reason}` })
}
const dupeSet = new Set(dupes.map(d => d.slug))
const polish = []
for (const p of setRes?.polish ?? []) {
  if (keptSet.has(p.slug) && !dupeSet.has(p.slug) && !polish.some(x => x.slug === p.slug)) polish.push(p)
}
for (const f of setRes?.build_failed ?? []) {
  if (!keptSet.has(f.slug) || dupeSet.has(f.slug)) continue
  const fix = `walldye build failed: ${f.error}. Make \`uv run walldye check ${f.slug}\` pass.`
  const known = polish.find(x => x.slug === f.slug)
  if (known) known.issue = `${fix} Then: ${known.issue}`
  else polish.push({ slug: f.slug, issue: fix })
}
log(`Set pass: ${dupes.length} duplicates to drop, ${polish.length} pieces to polish, ${(setRes?.near_clones ?? []).length} near-clone pairs`)

// ---- 4b. polish: rework -> judge ------------------------------------------

phase('Polish')
const judged = polish.length ? await pipeline(
  polish,
  (_, p) => agent(`${LOOK}
${tool()}

${LADDER}

${metaRules()}

Your design: ${p.slug}. Spec:
${spec([pieces[p.slug].idea])}
Seeing the whole set side by side, the art director flagged it: ${p.issue}
Substantially improve it; rewrite from scratch if that is better. At least 4 preview, Read, critique rounds, with a --crop detail check and the flexoki-light and nord renders. Compare against ${REFS} and the set sheets ${WORK}/set-*.png so it sits among the strongest pieces. Keep meta.yaml in step with what the piece now shows. End with \`uv run walldye check ${p.slug}\`.
Return a short summary of what changed and whether check passed.`, { label: `rework:${p.slug}`, phase: 'Polish', schema: REWORK }),
  async (rework, p) => {
    const verdict = await agent(`${LOOK}
You are an independent, demanding art director. Do NOT edit files.
Run \`uv run walldye preview ${p.slug}\` under fireproof (the default), --theme flexoki-light and --theme nord, Read each PNG, and do one --crop zoom into its busiest region. Run \`uv run walldye check ${p.slug}\`. Compare with ${REFS} and the set sheets ${WORK}/set-*.png (they show the piece before this rework).
Known prior problem: ${p.issue}
Designer's summary: ${rework ? rework.summary : '(the designer returned nothing; judge what is there)'}
Return score 1-10, check_ok, keep and a reason. keep only if the score is 7 or more, check passes and it is not a near-duplicate of another piece in the set.`, { label: `judge:${p.slug}`, phase: 'Polish', schema: JUDGE })
    return { p, rework, verdict }
  },
) : []

judged.forEach((j, i) => {
  const slug = polish[i].slug
  if (!j?.verdict) {
    log(`No verdict for ${slug}; keeping it for the owner's review`)
    return
  }
  pieces[slug].score = j.verdict.score
  if (!j.verdict.keep) dropped.push({ slug, stage: 'polish', reason: j.verdict.reason })
})

const droppedSet = new Set(dropped.map(d => d.slug))
const survivors = kept.filter(s => !droppedSet.has(s))
const leftovers = uniq(dropped.map(d => d.slug))
const cleanup = leftovers.length ? await dropFolders(leftovers) : null
log(`${survivors.length} pieces go on to sources and copy`)
if (!survivors.length) {
  return { status: 'nothing-kept', work: WORK, dropped, cleanup, near_clones: setRes?.near_clones ?? [], next: ['Nothing survived the set pass. Read `dropped` for why.'] }
}

// ---- 5. sources -----------------------------------------------------------

phase('Sources')
const sourcedGroups = await parallel(chunk(survivors, 3).map(group => () => agent(`You verify the sources of new wallpapers before they are published. You are in the walldye repo.
For each piece below:
1. Read wallpapers/<slug>/meta.yaml and design.py, and look at the piece (\`uv run walldye preview <slug>\`, Read the PNG), so you know what was actually built. The leads were written for the idea, and the piece may have drifted from it.
2. For every lead, WebFetch its url (load WebFetch and WebSearch with ToolSearch if they are deferred). With no url, or a url that fails, you may WebSearch for a page about that exact work and use its url. Keep a lead only when a fetched page confirms the work; correct title, author and year from that page. A site that blocks bots (403 or 429) may stay if a search result confirms the page. Drop everything else, and drop leads that no longer match what the piece shows.
3. kind: recreation only when the piece deliberately redraws that specific work (the owner must then choose a licence for it, so don't use it loosely); inspiration when the work inspired the idea; reference for background on a technique, genre, place or phenomenon; data for a dataset the piece plots.
4. Write the kept list as \`sources:\` in wallpapers/<slug>/meta.yaml: each item has kind, then title, author, year (a number) and url when known. A title names a work: the site italicises it, so a studio or artist with no single work gets author and no title. Titles are plain text with no asterisks or quotes. Change nothing else in the file, add no license line, and edit no other file.
Never run \`walldye build\`. Return, per piece, the sources you wrote and the leads you dropped with the reason.
PIECES AND LEADS:
${json(group.map(s => ({ slug: s, leads: pieces[s].idea.leads })))}`, { label: `sources:${group.join(',')}`, phase: 'Sources', schema: SOURCED })))

const sources = {}
for (const r of sourcedGroups) for (const d of r?.designs ?? []) if (survivors.includes(d.slug)) sources[d.slug] = d
const unsourced = survivors.filter(s => !sources[s])
if (unsourced.length) log(`No sources result for ${unsourced.join(', ')}; their meta.yaml keeps sources: []`)

// ---- 6. copy --------------------------------------------------------------

phase('Copy')
const copy = await agent(`You are the copy editor for a batch of new wallpapers. Load the avoid-ai-tropes skill first.
Pieces: ${survivors.join(' ')}
For each, read wallpapers/<slug>/meta.yaml (title, description, notes) and the one-line module docstring of wallpapers/<slug>/design.py. Then read all the descriptions side by side.
${COPY_RULES}
- Across the set: vary sentence shape and length, don't open two descriptions the same way, and drop any stock phrase that repeats from piece to piece. Two short sentences often read better than one long comma chain.
- Each description stays true to the piece: preview one when unsure (\`uv run walldye preview <slug>\`, Read the PNG). The preview output also flags colour words in the docstring and meta.yaml copy.
Edit in place: only title, description and notes in meta.yaml, and the module docstring in design.py (never code, facets or sources). Only these pieces' folders. Never run \`walldye build\`.
Return every change as {slug, field, before, after}.`, { label: 'copy', phase: 'Copy', schema: COPY })
if (!copy) log('The copy agent returned nothing; the builders\' copy stands')

// ---- 7. licences, build, verify -------------------------------------------

phase('Build')
const recreations = survivors.filter(s => sources[s]?.sources.some(x => x.kind === 'recreation'))
const licenseFor = s => {
  const own = LICENSES[s]
  if (typeof own === 'string' && own) return own
  const fallback = LICENSES['*']
  return recreations.includes(s) && typeof fallback === 'string' && fallback ? fallback : undefined
}
const licensed = survivors.filter(licenseFor).map(s => ({ slug: s, license: licenseFor(s) }))
const pending = recreations.filter(s => !licenseFor(s)).map(s => ({
  slug: s,
  recreates: sources[s].sources.filter(x => x.kind === 'recreation'),
}))

const summary = () => survivors.map(s => ({
  slug: s,
  score: pieces[s].score,
  light: pieces[s].light,
  aspects: pieces[s].aspects,
  variants: pieces[s].variants,
  sources: sources[s]?.sources.length ?? null,
}))

if (pending.length) {
  log(`Licence needed before walldye build. These pieces recreate a specific work, so the owner must choose each one's license (an SPDX id with a LICENSES/<id>.txt, e.g. CC0-1.0): ${pending.map(p => `${p.slug} (after ${p.recreates.map(r => [r.author, r.title].filter(Boolean).join(', ')).join('; ')})`).join(' | ')}`)
  return {
    status: 'needs-license',
    work: WORK,
    pieces: summary(),
    license: { pending, applied: licensed },
    dropped,
    cleanup,
    near_clones: setRes?.near_clones ?? [],
    copy: copy?.changes ?? null,
    next: [
      `Ask the owner which licence each of ${pending.map(p => p.slug).join(', ')} should carry (license.pending lists the works they recreate).`,
      `Add \`license: <id>\` to each one's wallpapers/<slug>/meta.yaml${licensed.length ? `, and to ${licensed.map(l => `${l.slug} (${l.license})`).join(', ')} as args.licenses asked` : ''}.`,
      `uv run walldye build ${survivors.join(' ')}   (with run_in_background; it checks the pieces in parallel)`,
      'uv run walldye build --verify   (with run_in_background)',
      `uv run walldye review ${survivors.join(' ')}   (with run_in_background; it blocks until the owner presses Done)`,
      'Confirm with the owner before dropping any rejected piece; commit the folders and wallpapers/index.json (drafts land on main as draft: true).',
    ],
  }
}

const final = await agent(`You run the final build for a batch of new wallpapers in the walldye repo. The drafts were built once before a polish and copy pass, so some are stale.
1. ${licensed.length ? `Licences the owner chose: ${licensed.map(l => `${l.slug}: ${l.license}`).join(', ')}. For each, add \`license: <id>\` to wallpapers/<slug>/meta.yaml on its own line after \`model:\`. Change nothing else.` : 'No licences to add: skip to step 2.'}
2. Build ${survivors.join(' ')}. ${TIMING} ${buildJobs(survivors, 'final')} Pieces that are current print "up to date". Record each failing slug with its error lines.
3. \`walldye build --verify\` re-renders every committed template of every version of every piece and writes nothing. Run it over every piece in the background, \`uv run walldye build --verify > ${WORK}/verify.log 2>&1\`, and ${waitFor('[w]alldye build')}. Each piece prints "<slug>: ok", "<slug>: DRIFT" with the reason on the lines below, or "<slug>: not built". Record each DRIFT and "not built" (\`grep -A3 -E 'DRIFT|not built' ${WORK}/verify.log\`).
Don't edit designs to make things pass, don't drop anything, don't commit. Return licensed, built (every slug that built or was up to date), failed, verify_ok, drift and the tail of the output.`, { label: 'build', phase: 'Build', schema: FINAL, effort: 'low' })

if (!final) {
  return {
    status: 'build-unknown',
    work: WORK,
    pieces: summary(),
    license: { applied: licensed },
    dropped,
    cleanup,
    near_clones: setRes?.near_clones ?? [],
    copy: copy?.changes ?? null,
    next: [
      `The build agent returned nothing. Check that ${licensed.length ? 'the license lines went in and ' : ''}\`uv run walldye build ${survivors.join(' ')}\` passes and \`uv run walldye build --verify\` shows no drift (both with run_in_background), then run \`uv run walldye review ${survivors.join(' ')}\` in the background.`,
    ],
  }
}
const built = survivors.filter(s => final.built.includes(s))
if (final.failed.length) log(`walldye build failed for ${final.failed.map(f => f.slug).join(', ')}`)
if (!final.verify_ok) log(`walldye build --verify reported drift: ${final.drift.join('; ')}`)

// ---- 8. human review ------------------------------------------------------

phase('Review')
let review = null
let lessons = null
if (A.review === false) {
  log('Review skipped (args.review is false)')
} else if (built.length) {
  log(`Review page for ${built.length} drafts: http://127.0.0.1:${REVIEW_PORT}/ (it waits until the owner presses Done, at most 2 hours)`)
  review = await agent(`Start the owner's review of new wallpaper drafts and wait for it to finish. You are in the walldye repo. \`walldye review\` serves a page on localhost, opens the browser, and blocks until the owner presses Done (at most 2 hours), then prints a JSON summary.
1. Start it with Bash run_in_background: \`uv run walldye review ${built.join(' ')} --port ${REVIEW_PORT} > ${WORK}/review.out 2>&1\`. The owner was told this port. Only if it fails because the port is taken, start it again with --port 0; the URL it prints is then the one to return.
2. Wait without ending your turn. Repeat \`timeout 580 tail --pid=$(pgrep -of '[w]alldye review') -f /dev/null; tail -c 6000 ${WORK}/review.out\` with a 600000 ms Bash timeout until the output ends with the JSON summary (it has a "finished" key). Never kill the process: the owner is deciding.
3. If there is no background Bash, run \`uv run walldye review ${built.join(' ')} --port ${REVIEW_PORT} --timeout 570\` in the foreground instead (600000 ms timeout), and repeat it with \`--no-open\` added until "finished" is true or 2 hours have passed. Decisions persist between runs.
Return the summary: url (from the first output line), finished, approved, rejected, undecided, notes as [{slug, note}], published, refused and error. If review exits at once (for example "not built: ..."), return finished false with that message as error.`, { label: 'review', phase: 'Review', schema: REVIEWED, effort: 'low' })
  if (!review) log('The review agent returned nothing')

  if (review && (review.approved.length || review.rejected.length)) {
    const reviewed = uniq([...review.approved, ...review.rejected.map(r => r.slug)]).filter(s => pieces[s])
    const res = await agent(`Turn the owner's review of a wallpaper batch into lessons for the next batch: what kinds of pieces survived, what kinds died, and why. Be specific about subjects, techniques and composition. Write a short plain paragraph or two, no colour names, in the manner of:
"Kept: instruments and science pieces (radar, oscilloscope, Smith chart), quiet textures with a small accent event (Penrose, hitomezashi), crisp patent-style technical drawings, a few bold graphics. Loves dither, pixel art and glyph art. Rejected: big saturated flat accent masses, clip-art-ish illustrations (single tree, iceberg, snowflake), maximalist low-poly landscapes, busy full-sheet blueprints."
${LESSONS}
REVIEW: ${json({ approved: review.approved, rejected: review.rejected, notes: review.notes ?? [] })}
PIECES: ${json(reviewed.map(s => ({ slug: s, concept: pieces[s].idea.concept, facets: pieces[s].idea.facets, critic_score: pieces[s].score })))}`, { label: 'lessons', phase: 'Review', schema: LESSONS_OUT, effort: 'low' })
    lessons = res?.lessons ?? null
  }
}

const next = []
if (final.failed.length) next.push(`Fix or drop ${final.failed.map(f => f.slug).join(', ')}: walldye build failed, so their build/ output is stale or missing and CI would fail.`)
if (!final.verify_ok) next.push('Look at the `walldye build --verify` drift before committing.')
if (!review && A.review !== false && built.length) next.push(`Run \`uv run walldye review ${built.join(' ')}\` with run_in_background.`)
if (A.review === false && built.length) next.push(`When the owner has time: \`uv run walldye review ${built.join(' ')}\` with run_in_background.`)
if (review?.rejected.length) next.push(`Confirm with the owner, then \`uv run walldye drop ${review.rejected.map(r => r.slug).join(' ')} --yes\`.`)
if (review?.undecided.length) next.push(`Undecided pieces stay draft: true; review them later with \`uv run walldye review ${review.undecided.join(' ')}\`.`)
if (review?.error) next.push(`walldye review ended with an error, so nothing was published: ${review.error}`)
if (review?.refused?.length) next.push(`Approval refused for ${review.refused.map(r => r.slug).join(', ')} (see review.refused).`)
next.push('Commit the new wallpapers/<slug>/ folders and wallpapers/index.json; drafts land on main as draft: true.')
if (lessons) next.push('Pass `lessons` as args.lessons to the next batch.')

return {
  status: review?.finished ? 'reviewed' : built.length ? 'built' : 'build-failed',
  work: WORK,
  pieces: summary(),
  license: { applied: licensed },
  dropped,
  cleanup,
  near_clones: setRes?.near_clones ?? [],
  copy: copy?.changes ?? null,
  build: final,
  review,
  lessons,
  next,
}

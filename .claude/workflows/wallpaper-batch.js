export const meta = {
  name: 'wallpaper-batch',
  description: 'Research, curate, build, prune and review a batch of new walldye wallpapers, landing as draft folders',
  whenToUse: 'The owner wants new wallpapers invented: researched, curated and built as a batch. When the owner names the subjects, use the walldye skill instead. args: {count, brief?, lenses?, licenses?, stop?, cut?, review?}; .claude/workflows/README.md explains each.',
  phases: [
    { title: 'Setup', detail: 'existing names, reference sheets, taxonomy' },
    { title: 'Research', detail: 'one idea agent per lens' },
    { title: 'Curate', detail: 'one art director picks count x 1.25' },
    { title: 'Design', detail: 'per batch of 3: builder, critic, fixer' },
    { title: 'Set', detail: 'build the drafts, near-clones, contact sheets' },
    { title: 'Polish', detail: 'rework and judge the weakest, drop the rest' },
    { title: 'Sources', detail: 'fetch every lead, per group of 3' },
    { title: 'Copy', detail: 'one pass over all new copy' },
    { title: 'Build', detail: 'licenses, walldye build' },
    { title: 'Review', detail: 'walldye review, then proposed lessons' },
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

const DEFAULT_BRIEF = 'No brief beyond the owner\'s taste in .claude/skills/walldye/references/taste.md.'
const SKILL = '.claude/skills/walldye'

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
const LIGHT = { type: 'string', enum: ['tokens', 'choice', 'branch'] }
const LEAD = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['recreation', 'inspiration', 'reference', 'data'] },
    title: { type: 'string', description: 'the name of a work: a game, film, book, paper, article or artwork' },
    topic: { type: 'string', description: 'the name of anything else: a technique, phenomenon, place, product, program or logo' },
    author: str,
    year: { type: 'integer' },
    url: str,
  },
  required: ['kind'],
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
  composition: { type: 'string', description: 'placement on a 1920x1080 canvas, negative space, what is gray and what is accent' },
  method: { type: 'string', description: 'how to generate it procedurally in Python' },
  inspiration: { type: 'string', description: 'artist, movement or phenomenon' },
  franchise: { type: 'string', description: 'the game, film or other franchise whose assets or look the piece depends on, making it fan work; empty when none' },
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
        properties: { ...IDEA_PROPS, why: { type: 'string', description: 'how it differs from its nearest neighbor' } },
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
    output: str,
  },
  required: ['licensed', 'built', 'failed'],
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
    edit: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, variant: str, published: { type: 'boolean' }, note: str }, required: ['slug', 'variant'] },
    },
    notes: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, variant: str, note: str }, required: ['slug', 'note'] },
    },
    edits: {
      type: 'array',
      items: { type: 'object', properties: { slug: str, variant: str, field: str, before: {}, after: {} }, required: ['slug', 'field'] },
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
const LESSONS_OUT = {
  type: 'object',
  properties: {
    proposals: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string', enum: ['principles.md', 'taste.md'] },
          change: { type: 'string', description: 'the line to add or the replacement, as it would read in the file' },
          why: { type: 'string', description: 'the note or edit it comes from, with the slug' },
        },
        required: ['file', 'change', 'why'],
      },
    },
  },
  required: ['proposals'],
}

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

const LOOK = `THE FAMILY LOOK: read ${SKILL}/references/taste.md (what the owner likes and rejects, and the fan-work rule) and ${SKILL}/references/principles.md (the house style, subjects, critique checklist and scoring) before anything else. Every piece works under any three seed colors, sits behind windows, and is judged under fireproof, flexoki-light and nord.
The owner's brief for this batch: ${BRIEF}`

const tool = () => `TOOLING (you are in the walldye repo; run every command from its root):
- Read ${SKILL}/SKILL.md and follow its steps 2 to 8 for each of your designs, with ${SKILL}/references/api.md and the nearest piece in SKILL.md's Examples table. Its meta.yaml, Copy and Variant policy sections apply, and so do docs/wallpapers.md and docs/api.md, which it points to.
- Look at ${REFS} before designing, and match the restraint and finish you see there.
- Batch rules, which override the skill: create or edit only wallpapers/<your slugs>/ (design.py, meta.yaml). Never touch walldye/, taxonomy.yaml, other wallpapers, wallpapers/index.json or any build/ folder. Never run \`walldye build\`, \`drop\` or \`review\`, and don't start the skill's critic: this workflow runs its own. Always name your own slugs in preview, check and render. No git commands that change state.
- ${TIMING} Give each check a 600000 ms Bash timeout.`

const VARIANTS = `VARIANTS: the Variant policy in ${SKILL}/SKILL.md. Usually none; at most 3 per piece, each draft: true.`

const COPY_RULES = `COPY RULES: Copy in docs/wallpapers.md, and Copy in ${SKILL}/SKILL.md on top of it.`

// A function because TAXONOMY is only known after setup.
const metaRules = () => `META.YAML: meta.yaml in ${SKILL}/SKILL.md and in docs/wallpapers.md. The taxonomy values are ${TAXONOMY}; a missing value goes under proposed_facets. Leave sources: [] and add no license line: a later agent verifies the leads and writes the sources.
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
3. Reference sheets. Pick about 30 pieces that match .claude/skills/walldye/references/taste.md (dither, pixel, glyph, instrument and technical-drawing pieces; skip the fan pieces, whose meta.yaml has \`franchise:\`) and sheet them as the family: \`uv run walldye sheet <slugs> --cols 6 -o WORK/reference.png\`. Then sheet the whole catalog small, for spotting look-alikes: \`uv run walldye sheet --all --cols 12 --thumb 160 -o WORK/catalog.png\`. Read both PNGs to confirm they rendered. Return the path of reference.png as references.
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
EXISTING DESIGNS (do not duplicate; a riff is fine only if clearly distinct): Read ${WORK}/existing.txt and look at ${WORK}/catalog.png, a sheet of every piece. Review dropped the ideas listed under "Dropped in review" in ${SKILL}/references/ideas.md: don't propose them again as they were. Look at ${REFS}: that is the family.

YOUR LENS: ${l.territory}

1. Research first: roughly 8-15 web searches or fetches surveying your lens for specific works, visual ideas and techniques (load WebSearch and WebFetch with ToolSearch if they are deferred). Concrete references beat generic ones.
2. Brainstorm ${PER_LENS} concepts that fit THE FAMILY LOOK. Range matters: vary scale (tiny focal object vs full-bleed texture), placement, density and technique. No clusters of variants of one idea.
3. Give each a concrete composition (placement on a 1920x1080 canvas, what is gray and what is accent) and a concrete Python-to-SVG method.
4. facets: technique, subject and lineage values from taxonomy.yaml (${TAXONOMY}). When nothing fits, use a new lowercase slug; it becomes a proposal for the owner.
5. leads: the specific works, papers, datasets or pages behind the idea, as {kind, title or topic, author, year, url}: a title names a work, a topic anything else. kind is recreation (the piece would redraw that specific work, allowed only for works in the public domain or under an open license; a work still in copyright is an inspiration, and the idea may keep its spirit but must make two or three deliberate departures of its own, never a copy of the composition), inspiration, reference (a technique or phenomenon) or data (a dataset it plots). Give a url only when you found one. A later agent fetches every lead and drops the ones that don't check out, so never invent one.
6. franchise: the game, film or other franchise whose assets or look the idea depends on, which makes it fan work (taste.md, Fan work); leave it empty otherwise. The script drops fan work unless the owner's brief names the franchise, so prefer subjects that are free: a game's rules or a real game record drawn as a system, not its assets.
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
- Nothing that duplicates an EXISTING design at thumbnail size: Read ${WORK}/existing.txt and look at ${WORK}/catalog.png. Names must not collide with any name in existing.txt.
- Diversity: at most ${CAP} of the selected ideas may share any one technique facet value (10% of ${TARGET}, and at least one); an idea with two technique values counts towards both. Mix roughly 55% focal-object compositions, 30% quiet full-bleed textures with an accent event and 15% bold graphic or poster pieces. Vary focal placement (not everything right of center).
- Reject anything off-look: other hues, photos, filters, loud or busy behind windows.
- No fan work unless the brief names its franchise (taste.md, Fan work), and nothing from the "Dropped in review" list in ${SKILL}/references/ideas.md. Keep each idea's franchise field as the researcher set it.
- Feasibility: buildable in Python to a template under 600 kB. Rewrite vague methods concretely.
- Tighten each composition so a designer can build it without guessing: positions, rough sizes, which elements are accent and which gray.
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
  else if (raw.franchise?.trim() && !BRIEF.toLowerCase().includes(raw.franchise.trim().toLowerCase())) problem = `fan work (${raw.franchise.trim()}) the brief does not ask for`
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

${VARIANTS}

${metaRules()}

YOUR DESIGNS: ${names(batch)}. Their specs are at the end.
For each design, run SKILL.md's steps 2 to 8:
- \`walldye new\` with your model id. If it says the folder already exists, the folder is yours from an interrupted run of this batch: continue from it.
- The spec is a starting point, not a cage: if something reads poorly at wallpaper scale, change it in the spirit of the concept.
- End with a full fireproof preview, \`uv run walldye check <slug>\` ending in "1/1 ok", and ruff and Pyrefly reporting no errors.
Return one entry per design: status done or failed; size_kb of the 16:9 render if you measured it; light = the ladder step you ended on (tokens, choice, branch); aspects = ["any"] or the aspects tuple in @design, as a list ([] for 16:9 only); variants = the names of the draft variants you proposed ([] for none); meta_ok = meta.yaml filled as META.YAML says and check reports no meta.yaml errors; notes = what you built, key decisions, anything the critic should know.

SPECS:
${spec(batch)}`, { label: `design:${names(batch, ',')}`, phase: 'Design', schema: BUILT }),

  async (built, batch) => {
    const b = byKey(built?.designs, 'name')
    const done = batch.filter(s => b[s.name]?.status === 'done')
    if (!done.length) return { built: b, done, reviews: null }
    const critique = await agent(`You are a demanding art director reviewing new wallpapers for a curated set. Do NOT edit any files.
${LOOK}
${VARIANTS}

${metaRules()}

Look at ${REFS} first. For each design (${names(done)}):
- \`uv run walldye preview <slug>\` (fireproof, the template), then with --theme flexoki-light and --theme nord. Read every PNG.
- One --crop X,Y,W,H into its busiest region, and --width 480 for the thumbnail read.
- If design.py declares aspects, also --aspect 32:9 and --aspect 9:19.5.
- For each variant in \`@design(variants=...)\`, a preview with --variant <name>.
- Read design.py and meta.yaml.
Judge: does it read instantly; is the composition deliberate; is the accent a restrained event; are the grays quiet enough behind windows; is it clean at 4K (no artifacts, jaggies, awkward clipping, muddy tone steps); does it feel like a sibling of the reference set? Faint is the common failure, more than loud: call it out when the idea only shows up zoomed in.
Light: does the flexoki-light render hold up (tone steps visible, the event still reads, no shadow that turned into a glare) and does the event survive nord's cool accent by shape and size? Is the light ladder step (SKILL.md step 5) the lowest that works? light_verdict is ok or fix; put light fixes in fixes, prefixed "light:".
Variants: judge each proposed variant against VARIANTS. Does it change what is depicted, is it as strong as the default, and does it look different at thumbnail size? A variant that passes check can still be a nudge of one value: drop it if the subject did not change. Return one verdict per variant in variants (keep false with the reason drops it); [] when the design has none.
Copy: check title, description, alt text, notes, variant labels, descriptions and alt texts, and the docstring against the COPY RULES, asking of each: is its fact checkable, does anything but the alt text describe the picture, and would a person say it out loud? Each copy_fixes entry quotes the replacement text.
Score 1-10 by the scoring in principles.md. verdict keep only for 8+ with no meaningful fixes; fix for fixable issues; rework if the approach fails. Fixes must be concrete (positions, sizes, tones, density), most important first.
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

${VARIANTS}

${metaRules()}

REVIEWS:
${json(reviews)}
For each design above: apply the fixes, the light fixes and the copy_fixes (for rework, rethink the approach but keep the concept), and remove every variant whose verdict has keep false from design.py and meta.yaml. Then preview, Read and revise for at least 2 rounds, including --theme flexoki-light and --theme nord, ending with SKILL.md's step 8 passing (check, ruff and Pyrefly).
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
  if (!res) log(`The drop agent returned nothing; these folders may still exist: ${slugs.join(', ')}`)
  return res
}

const cleanupAndReturn = async (status, extra) => {
  const leftovers = uniq(dropped.map(d => d.slug))
  const res = leftovers.length ? await dropFolders(leftovers) : null
  return { status, work: WORK, dropped, cleanup: res, ...extra }
}

if (!kept.length) {
  return await cleanupAndReturn('nothing-kept', { next: ['No design survived critique. Read `dropped` for why, adjust the brief, and run again.'] })
}

phase('Set')
const scored = kept.map(s => ({ slug: s, score: pieces[s].score, light: pieces[s].light, notes: pieces[s].notes }))
const setRes = await agent(`You run the set-level pass over a batch of new wallpapers. The per-design critics never saw the set; you do.
${LOOK}
NEW PIECES (slug, critic score, light ladder step, designer notes):
${json(scored)}

You may run \`walldye build\` (the designers could not). ${TIMING}
1. Build every new piece. ${buildJobs(kept, 'set')} Note each slug that fails, with its error lines. Do not fix designs yourself.
2. Near-clones: \`uv run python -c "from walldye.tools.similar import near_clones; near_clones('${kept.join(' ')}'.split())"\`. This is the near-clone pass of \`walldye check --similar\` without the full check that build just ran. It compares each new piece's build/16x9.svg (the default version) with every built piece and prints \`similar (0.95): a ~ b\` per close pair (nothing when there are none), then \`similar: skipped, no build/16x9.svg: ...\` for the pieces that failed to build. It compares ink maps, so it misses motif-level duplicates (two different mountain pieces); trust your eyes over it, both ways.
3. Contact sheets in pages of 30: \`uv run walldye sheet <slugs> --cols 6 -o ${WORK}/set-<page>.png\`, and each page again with \`--theme flexoki-light -o ${WORK}/set-<page>-light.png\`. Read every page next to ${REFS} and ${WORK}/catalog.png. Hunt for look-alikes (within the batch and against existing pieces), weak thumbnails, tone that drifts from the family, too many focal points in the same spot, and light renders that fall apart.
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

${metaRules()}

Your design: ${p.slug}. Spec:
${spec([pieces[p.slug].idea])}
Seeing the whole set side by side, the art director flagged it: ${p.issue}
Substantially improve it; rewrite from scratch if that is better. At least 4 preview, Read, critique rounds, with a --crop detail check and the flexoki-light and nord renders. Compare against ${REFS} and the set sheets ${WORK}/set-*.png so it sits among the strongest pieces. Keep meta.yaml in step with what the piece now shows. End with SKILL.md's step 8 passing (check, ruff and Pyrefly).
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
3. kind: recreation only when the piece deliberately redraws that specific work and that work is in the public domain or openly licensed (the owner must then choose a license for it, so don't use it loosely). If a piece redraws a work still in copyright, keep the lead as inspiration and flag the piece in your reply as needing rework; inspiration when the work inspired the idea; reference for background on a technique, genre, place or phenomenon; data for a dataset the piece plots.
4. Write the kept list as \`sources:\` in wallpapers/<slug>/meta.yaml: each item has kind, then title or topic, author, year (a number) and url when known. A title names a work (a game, film, book, paper, article or artwork) and the site italicizes it; anything else (a technique, phenomenon, place, building, product, program, logo or wiki entry) is a topic, set upright. A studio or artist with no single work gets author and neither. Titles and topics are plain text with no asterisks or quotes. A piece with a data/ folder needs a data source, or the recreation its files come from. Change nothing else in the file, add no license line, and edit no other file.
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
For each, read wallpapers/<slug>/meta.yaml (title, description, alt, notes and each version's description and alt) and the one-line module docstring of wallpapers/<slug>/design.py. Then read all the descriptions side by side.
${COPY_RULES}
- Across the set: don't open two descriptions the same way, and drop any phrase that repeats from piece to piece.
- Each description's fact checks out against the piece's sources; each alt text matches the picture: preview when unsure (\`uv run walldye preview <slug>\`, Read the PNG). The preview output also flags copy problems in the docstring and meta.yaml.
Edit in place: only title, description, alt and notes in meta.yaml (and each version's description and alt), and the module docstring in design.py (never code, facets or sources). Only these pieces' folders. Never run \`walldye build\`.
Return every change as {slug, field, before, after}.`, { label: 'copy', phase: 'Copy', schema: COPY })
if (!copy) log('The copy agent returned nothing; the builders\' copy stands')

// ---- 7. licenses and build -----------------------------------------------

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
  log(`License needed before walldye build. These pieces recreate a specific work, so the owner must choose each one's license (an SPDX id with a LICENSES/<id>.txt, e.g. CC0-1.0): ${pending.map(p => `${p.slug} (after ${p.recreates.map(r => [r.author, r.title].filter(Boolean).join(', ')).join('; ')})`).join(' | ')}`)
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
      `Ask the owner which license each of ${pending.map(p => p.slug).join(', ')} should carry (license.pending lists the works they recreate).`,
      `Add \`license: <id>\` to each one's wallpapers/<slug>/meta.yaml${licensed.length ? `, and to ${licensed.map(l => `${l.slug} (${l.license})`).join(', ')} as args.licenses asked` : ''}.`,
      `uv run walldye build ${survivors.join(' ')}   (with run_in_background; it checks the pieces in parallel)`,
      `uv run walldye review ${survivors.join(' ')}   (with run_in_background; it blocks until the owner presses Apply)`,
      'Confirm with the owner before dropping any rejected piece. Leave the folders uncommitted, and offer a commit that stages only them (drafts land on main as draft: true).',
    ],
  }
}

const final = await agent(`You run the final build for a batch of new wallpapers in the walldye repo. The drafts were built once before a polish and copy pass, so some are stale.
1. ${licensed.length ? `Licenses the owner chose: ${licensed.map(l => `${l.slug}: ${l.license}`).join(', ')}. For each, add \`license: <id>\` to wallpapers/<slug>/meta.yaml on its own line after \`model:\`. Change nothing else.` : 'No licenses to add: skip to step 2.'}
2. Build ${survivors.join(' ')}. ${TIMING} ${buildJobs(survivors, 'final')} Pieces that are current print "up to date". Record each failing slug with its error lines.
Don't edit designs to make things pass, don't drop anything, don't commit. Return licensed, built (every slug that built or was up to date), failed and the tail of the output.`, { label: 'build', phase: 'Build', schema: FINAL, effort: 'low' })

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
      `The build agent returned nothing. Check that ${licensed.length ? 'the license lines went in and ' : ''}\`uv run walldye build ${survivors.join(' ')}\` passes (with run_in_background), then run \`uv run walldye review ${survivors.join(' ')}\` in the background.`,
    ],
  }
}
const built = survivors.filter(s => final.built.includes(s))
if (final.failed.length) log(`walldye build failed for ${final.failed.map(f => f.slug).join(', ')}`)

// ---- 8. human review ------------------------------------------------------

phase('Review')
let review = null
let lessons = null
if (A.review === false) {
  log('Review skipped (args.review is false)')
} else if (built.length) {
  log(`Review page for ${built.length} drafts: http://127.0.0.1:${REVIEW_PORT}/ (it waits until the owner presses Apply, at most 2 hours)`)
  review = await agent(`Start the owner's review of new wallpaper drafts and wait for it to finish. You are in the walldye repo. \`walldye review\` serves a page on localhost, opens the browser, and blocks until the owner presses Apply (at most 2 hours), then prints a JSON summary.
1. Start it with Bash run_in_background: \`uv run walldye review ${built.join(' ')} --port ${REVIEW_PORT} > ${WORK}/review.out 2>&1\`. The owner was told this port. Only if it fails because the port is taken, start it again with --port 0; the URL it prints is then the one to return.
2. Wait without ending your turn. Repeat \`timeout 580 tail --pid=$(pgrep -of '[w]alldye review') -f /dev/null; tail -c 6000 ${WORK}/review.out\` with a 600000 ms Bash timeout until the output ends with the JSON summary (it has a "finished" key). Never kill the process: the owner is deciding.
3. If there is no background Bash, run \`uv run walldye review ${built.join(' ')} --port ${REVIEW_PORT} --timeout 570\` in the foreground instead (600000 ms timeout), and repeat it with \`--no-open\` added until "finished" is true or 2 hours have passed. Decisions persist between runs.
Return the summary: url (from the first output line), finished, approved, rejected, undecided, edit as [{slug, variant, published, note}], notes as [{slug, variant, note}], edits as [{slug, variant, field, before, after}], published, refused and error. If review exits at once (for example "not built: ..."), return finished false with that message as error.`, { label: 'review', phase: 'Review', schema: REVIEWED, effort: 'low' })
  if (!review) log('The review agent returned nothing')

  if (review && (review.approved.length || review.rejected.length || review.edit?.length)) {
    const reviewed = uniq([...review.approved, ...review.rejected.map(r => r.slug), ...(review.edit ?? []).map(e => e.slug)]).filter(s => pieces[s])
    const res = await agent(`Turn the owner's review of a wallpaper batch into proposed changes to the walldye skill's references, as step 12 of ${SKILL}/SKILL.md describes. Read ${SKILL}/references/principles.md and ${SKILL}/references/taste.md first. Edit no files: the owner approves each proposal.
For each note and each copy edit, ask whether it would apply to other pieces too. When it would, propose one change: a failure row or checklist item in principles.md, with this piece as the example, or a line in taste.md. Skip what the files already say, and notes about one piece alone ("move the moon left"). Versions sent back for an edit were worth keeping but not yet right; notes on approved versions often ask for more of the same. No color names.
REVIEW: ${json({ approved: review.approved, rejected: review.rejected, sent_back_for_edit: review.edit ?? [], notes: review.notes ?? [], edits: review.edits ?? [] })}
PIECES: ${json(reviewed.map(s => ({ slug: s, concept: pieces[s].idea.concept, facets: pieces[s].idea.facets, critic_score: pieces[s].score })))}`, { label: 'lessons', phase: 'Review', schema: LESSONS_OUT, effort: 'low' })
    lessons = res?.proposals?.length ? res.proposals : null
  }
}

const next = []
if (final.failed.length) next.push(`Fix or drop ${final.failed.map(f => f.slug).join(', ')}: walldye build failed, so they cannot be reviewed, and CI would fail once they are published.`)
if (!review && A.review !== false && built.length) next.push(`Run \`uv run walldye review ${built.join(' ')}\` with run_in_background.`)
if (A.review === false && built.length) next.push(`When the owner has time: \`uv run walldye review ${built.join(' ')}\` with run_in_background.`)
if (review?.rejected.length) next.push(`Confirm with the owner, then \`uv run walldye drop ${review.rejected.map(r => r.slug).join(' ')} --yes\`.`)
if (review?.edit?.length) next.push(`The owner sent these back for changes; rework each as its note says, then build and review it again: ${review.edit.map(e => `${e.variant === 'default' ? e.slug : `${e.slug} (${e.variant})`}: ${e.note || 'no note'}`).join('; ')}.`)
if (review?.undecided.length) next.push(`Undecided pieces stay draft: true; review them later with \`uv run walldye review ${review.undecided.join(' ')}\`.`)
if (review?.error) next.push(`walldye review ended with an error, so nothing was published: ${review.error}`)
if (review?.refused?.length) next.push(`Approval refused for ${review.refused.map(r => r.slug).join(', ')} (see review.refused).`)
if (lessons) next.push('Show the owner `proposed_lessons`, and write the ones they approve into .claude/skills/walldye/references/.')
next.push(`Leave the new folders uncommitted. Offer the owner a commit that stages only wallpapers/{${survivors.join(',')}}/ and any lines review added to taxonomy.yaml; drafts land on main as draft: true.`)

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
  proposed_lessons: lessons,
  next,
}

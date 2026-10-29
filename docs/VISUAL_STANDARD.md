# Visual standard: from functional slides to art-directed motion design

Owner verdict (2026-10-29): scenes that pass the checks still look like PowerPoint: text, boxes,
circles, fades. The target is the ambition of good YouTube documentaries, sports docs, cinematic
explainers and editorial motion graphics: a sequence of designed, animated SHOTS. Used by G6
(overhaul), G9 (profiles) and G12 (polish). Read it all before touching visuals.

## 1. Sections

1. Principles  2. Choose the medium  3. Techniques (capabilities, not a checklist)  4. PowerPoint
warning signs  5. Art-direction brief  6. Theme vs composition vs animation  7. Performance on the i5
8. Review loop  9. Benchmark  10. Reliability and safety  11. Definition of success  12. If you drift

## 1. Principles

- Treat the whole canvas as a designed environment, not a background for floating cards.
- Do not confuse complexity with quality. Every choice must serve the story, clarity, mood or impact.
- A quiet, atmospheric scene can look expensive. Not every scene is flashy.
- Intentional art direction, visual variety, movement that communicates something.
- A scene is not good because it renders, animates, or uses several colours.

## 2. Choose the medium first

Not every narrated line needs a motion graphic. For each moment decide what serves the story best:
cinematic footage, a still with camera movement, kinetic typography, a custom infographic, a 2D illustrated
sequence, an atmospheric typographic scene, or a deliberate plain editorial cut. Pick per moment, then
build an original composition. The script's `motion.medium` records the choice (G6 step 4).

Example. Narration: "In just three years he went from overlooked to the most feared player in the league."
Slide version: sentence over a gradient + a stat. Directed version: open on a small isolated silhouette in
darkness; track across clippings, match stills and dates; build speed as the years advance; push into a
full-frame portrait; slam the key number on the strongest spoken word; leave the scene through the motion of the
type so it hands over to the next shot. A beginning, a development, a payoff.

## 3. Techniques (use when they serve the shot)

- Kinetic typography: text that moves, transforms, stretches, tracks, assembles, interacts with the frame.
- Layered compositions: footage, stills, type, graphics, textures, masks, foreground elements.
- Parallax and camera: depth, pans, pushes, pulls, dramatic reframing.
- Cinematic reveals: masked entrances, animated crops, wipes, split reveals, silhouettes, light sweeps.
- Data viz with dimension: animated charts, timelines, comparisons, rankings with strong hierarchy.
- Visual storytelling: metaphors, illustrated sequences, character-focused frames, transformations.
- Texture and atmosphere: tasteful grain, shadow, glow, gradient, lighting, particles, motion trails,
  restrained blur where affordable.
- Editorial pacing: anticipation, acceleration, impact, pauses, holds, transitions synced to the narration
  (`words` gives per-word frames).
- Mood range: restrained, explosive, technical, elegant, playful, dramatic, chosen by the story.

## 4. PowerPoint warning signs (when they become the DEFAULT)

Rounded rectangles with headings/bullets; repeated 3- or 4-card layouts; the same title+subtitle+icon in every
scene; circles and lines that only decorate empty space; generic dashboards/UI panels; repeated fade-ins with no
meaningful movement; scenes that only swap text/colours/icons over the same composition; generic stock-template
look. Cards, boxes and simple charts are allowed when they are genuinely the best solution; they must not
dominate the identity.

Confirmed technical causes in the current engine (from the Phase 3 contract; re-verify in G6 step 1):
scenes cannot use images or footage (SVG/CSS only); the kit has charts/counters/rings/reveal text but no
camera, parallax, masks, layered media, light, grain, trails; the example scenes the prompt shows are card/ring
layouts; `motion` has no art-direction fields; the checks only prove "works".

## 5. Art-direction brief (lightweight; avoid production bureaucracy)

Per generated scene, short fields inside `motion` (all optional):
`concept` (the one visual idea), `medium`, `composition` (focal point; foreground / middle / background),
`beats` (what happens when, tied to narration words), `assets` (named stills/footage), `transition_in` /
`transition_out`, `cost`, plus the existing `brief` and `data`. The scene author must also state how this scene
differs from its neighbours. Prompts must ask: what should the audience feel or understand; dominant idea;
movement over time; relation of animation to narration; entry and exit.

## 6. Three layers (consistency without sameness)

- Brand / art direction (per video, `theme.json`): colour, type, texture, mood, lighting, motion language.
- Scene composition (per moment): the specific arrangement.
- Animation: how elements enter, transform, interact, exit.
Scenes in one video should feel related, not interchangeable. Different videos can have genuinely different
identities from subject, tone and the owner's instructions.

## 7. Performance (i5-8350U, 12 GB, no GPU)

Prefer deterministic, render-friendly techniques. Avoid expensive blur, big SVG filters, many particles. Cache
unchanged scenes (hash). Offer a preview quality; keep full-resolution output. Do not sacrifice quality
indiscriminately to save time: ration heavy effects with `cost` and use them where they pay off.
Record frames/s of the benchmark scenes in LOG.

## 8. Review loop (G5 tools)

Generate -> validate and render safely -> capture frames/sheet -> review composition, hierarchy, contrast,
cropping, density, movement -> revise only the weak scene -> cache the good ones. Easy inspection in the UI
Scenes tab or Remotion Studio. Automated metrics are facts, not taste. A technically valid scene is not
automatically a good scene; the owner has the final say.

## 9. Benchmark (G6 step 5): five visually distinct scene types, each >= 6 s, 16:9 and 9:16

1. Cinematic reveal: dramatic typography + layered imagery, a deliberate reveal.
2. Kinetic typography: expressive movement showing emphasis and rhythm.
3. Story timeline: chronological sequence that is NOT a row of static cards.
4. Data / statistical explainer: animated information, strong hierarchy, meaningful movement.
5. Atmospheric narrative: restrained, cinematic; composition, depth, subtle movement.
These are benchmark categories, not templates for future videos. Use local or clearly credited CC0 sample
assets; never invent movie footage; no paid APIs. Compare against the old output (`stat_ring`,
`timeline_reveal`) with before/after sheets. If the benchmark still looks like a presentation, G6 is not done.

## 10. Reliability and safety

Do not weaken the static check to allow complexity. Any new rendering capability gets a security review
(who can reach what: network, files, DOM). Preserve Python orchestration, timeline validation, voice, captions,
footage/still handling, readable errors, fallbacks, caching, 16:9 + 9:16, Premiere/VideoPad exports, project
files. Free-first, local-first.

## 11. Definition of success

Not "can render more elaborate scenes". The engine takes a narration and its context, creates distinct
art-directed sequences, animates them with intentional timing and composition, renders them reliably, and makes
weak scenes easy to review and improve, for ANY kind of video (documentary, sports, science, history, data
story, recap), not one visual formula.

## 12. If you drift (the owner's three rules)

1. Don't confuse more effects with better art direction.
2. Don't call a scene good because it compiles.
3. Show rendered evidence, not just code changes.
Also: do not solve it with a longer prompt alone; prompts, kit, examples and the review loop all shape output.

## Notes on how creators actually do this (context, not a spec)

Impressive "AI-made" edits are hybrid pipelines: AI plans the sequence, generates or finds assets, writes
animation code (After Effects / Remotion), a human reviews and refines weak parts. Four common routes: AI video
clips (Runway-style), AI directing motion-graphics code, AI assets + conventional editing, hybrid. For this
project: efficient Remotion + existing footage + stills + layered 2D + restrained effects first; 3D (Blender) or
AI video only when a scene truly needs it and the owner approves the cost. Realistic AI-generated scenes and
vector/kinetic-type graphics are different production problems; ask the owner which look they want and for 1-2
example videos before G6 step 5.

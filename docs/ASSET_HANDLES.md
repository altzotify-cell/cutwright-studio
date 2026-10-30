# Asset handles: how a scene names real footage (5.5B design, updated for the owner's go)

1. Scene: `<LayeredMedia asset="footage_a" />`. `asset` is a plain string literal matching `^[a-z][a-z0-9_]{0,31}$`
   (no template string, variable, `.mp4`, slash or URL); scenes still import only 'remotion', 'react', '@kit'.
2. Manifest: the top-level `assets` table IS the handle table (`{"id": "footage_a", "path": "...x.mp4", "origin":
   "footage"}`); the step declares `"assets": {"footage_a": "@asset.footage_a"}` as an input, which `@asset.<id>`
   resolves to an absolute path and digests into the step cache key - the footage's sha256 counts, as in M3/4A.
3. Executor: validate each handle (exists, extension -> video|image), stage it at `remotion/public/assets/<handle>.<ext>`
   as a HARD LINK (copy across volumes) - a symlink does not work: the bundler forwards it and the render answers
   404 - then MOUNT the same link into `<bundle>/public/assets/` on every render, so a reused bundle cannot serve a
   stale clip. The handle -> file table travels in the props file, NOT in a generated module.
4. Bundle: `remotion bundle --out-dir=<cache>` once per `sha256(kit/** + src/** + scenes_examples/** + config)`, then
   `still <bundle-dir>`; cache at `out/.cache/remotion-bundle/`, capped at 5, oldest by mtime deleted first.
5. An asset is digested ONCE per (path, size, mtime), never rehashed while it is unchanged; above 64 MiB it is
   identified by size+mtime only, as `guard.py` already does. Scenes use pre-cut clips, never a whole movie.
6. Kit: components only - `useAsset` is private to the kit and `index.ts` exports no resolver, so a scene cannot
   name a file. `LayeredMedia`/`Camera` use `Img`/`OffthreadVideo` INSIDE the kit; an undeclared handle throws.
7. Checker: `@kit` resolves to `kit/index.ts` in the real TS program, so an invented name is fatal (2305/2724) and
   `useAsset` is not importable at all; plus one rule: `asset` must be a literal naming a declared handle.
8. Measured 2026-10-30 on the i5: one bundle = 8.1 s, 53 files, 38.2 MB with a 4.4 MB clip mounted (19.9 MB without
   source maps), and the clip shares its inode with the original, so it costs 0 extra bytes. Three stills of the
   footage scene: 26.7 s wall cold (5.4/5.3/6.3 s of render), 1.9 s when the steps are cached; the old path was ~10 s
   per still. `--public-dir` is supported, but the bundler copies that folder into every bundle (`bundle.js:278`).


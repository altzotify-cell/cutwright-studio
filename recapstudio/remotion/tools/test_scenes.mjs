#!/usr/bin/env node
// Single-frame test render of scenes (gameplan 4b). Usage:  node tools/test_scenes.mjs <manifest.json>
//
//   manifest: {"out": "report.json", "outDir": "<where the PNGs go>", "browserExecutable": null,
//              "timeoutMs": 45000, "scenes": [{"id": "d_02", "composition": "scene-d-02"}]}
//   report:   {"ok": true, "bundleSeconds": 31.2,
//              "ref": {"landscape": "<png>", "portrait": "<png>"},
//              "scenes": {"d_02": {"landscape": {"frames": [{"frame": 0, "file": "<png>", "error": null}]},
//                                  "portrait":  {"frames": [...]}, "logs": ["..."]}}}
//
// It bundles Remotion ONCE, opens ONE browser and renders a few frames of every scene (start, 40 %, 75 %, last) at the
// project's shape, plus one frame at the other aspect ratio. A scene that throws shows up here with its real error.
// scenes.py then judges the PNGs (blank? drew nothing?). Frame files stay in outDir so you can look at them.

import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const {bundle} = require('@remotion/bundler');
const {openBrowser, renderStill, selectComposition, ensureBrowser} = require('@remotion/renderer');
const rdir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const manifest = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const timeout = manifest.timeoutMs ?? 45000;
fs.mkdirSync(manifest.outDir, {recursive: true});

const firstLine = (e) => String((e && e.message) || e || 'unknown error').split('\n').map((l) => l.trim()).filter(Boolean)[0] ?? 'unknown error';
const cleanMsg = (m) => m.replace(/^Error:\s*/, '').replace(/^Uncaught\s+/, '');

const report = {ok: false, bundleSeconds: 0, ref: {}, scenes: {}};
const finish = () => fs.writeFileSync(manifest.out, JSON.stringify(report, null, 2));

try {
  const t0 = Date.now();
  const serveUrl = await bundle({
    entryPoint: path.join(rdir, 'src', 'index.ts'),
    webpackOverride: (config) => ({
      ...config,
      resolve: {...config.resolve, alias: {...(config.resolve?.alias ?? {}), '@kit': path.join(rdir, 'kit')}},
    }),
  });
  report.bundleSeconds = Math.round((Date.now() - t0) / 100) / 10;

  if (!manifest.browserExecutable) await ensureBrowser();
  const browser = await openBrowser('chrome', {
    browserExecutable: manifest.browserExecutable || null,
    logLevel: 'error',
    chromiumOptions: {},
  });

  let logs = [];
  const onBrowserLog = (l) => {
    if ((l.type === 'error' || l.type === 'warning') && logs.length < 8) logs.push(cleanMsg(String(l.text)).slice(0, 300));
  };

  const still = async (compId, portrait, frame, file) => {
    const composition = await selectComposition({serveUrl, id: compId, inputProps: {portrait}, puppeteerInstance: browser, logLevel: 'error'});
    const f = Math.max(0, Math.min(frame === 'last' ? composition.durationInFrames - 1 : frame, composition.durationInFrames - 1));
    await renderStill({
      composition,
      serveUrl,
      frame: f,
      output: file,
      imageFormat: 'png',
      inputProps: {portrait},
      puppeteerInstance: browser,
      timeoutInMilliseconds: timeout,
      onBrowserLog,
      logLevel: 'error',
    });
    return composition.durationInFrames;
  };

  // the empty themed background, for the "scene drew nothing" comparison
  for (const portrait of [false, true]) {
    const file = path.join(manifest.outDir, `_ref_${portrait ? 'portrait' : 'landscape'}.png`);
    try {
      await still('scene-empty-ref', portrait, 0, file);
      report.ref[portrait ? 'portrait' : 'landscape'] = file;
    } catch (e) {
      /* the comparison is skipped when the reference is missing */
    }
  }

  for (const sc of manifest.scenes) {
    const rec = {landscape: {frames: []}, portrait: {frames: []}, logs: []};
    report.scenes[sc.id] = rec;
    logs = [];

    // project aspect: start, 40 %, 75 %, last. Stop at the first error (the same error repeats on every frame).
    let dur = null;
    try {
      const probe = await selectComposition({serveUrl, id: sc.composition, inputProps: {portrait: false}, puppeteerInstance: browser, logLevel: 'error'});
      dur = probe.durationInFrames;
    } catch (e) {
      rec.landscape.frames.push({frame: 0, file: null, error: cleanMsg(firstLine(e))});
    }
    if (dur !== null) {
      const marks = [...new Set([0, Math.round(dur * 0.4), Math.round(dur * 0.75), dur - 1])].filter((f) => f >= 0 && f < dur);
      for (const f of marks) {
        const file = path.join(manifest.outDir, `${sc.id}_f${String(f).padStart(4, '0')}.png`);
        try {
          await still(sc.composition, false, f, file);
          rec.landscape.frames.push({frame: f, file, error: null});
        } catch (e) {
          rec.landscape.frames.push({frame: f, file: null, error: cleanMsg(firstLine(e))});
          break;
        }
      }
      // the other aspect ratio, one frame (warning level: 9:16 polish is Phase 5)
      const failedLand = rec.landscape.frames.some((x) => x.error);
      if (!failedLand) {
        const file = path.join(manifest.outDir, `${sc.id}_portrait.png`);
        try {
          await still(sc.composition, true, Math.round(dur * 0.6), file);
          rec.portrait.frames.push({frame: Math.round(dur * 0.6), file, error: null});
        } catch (e) {
          rec.portrait.frames.push({frame: Math.round(dur * 0.6), file: null, error: cleanMsg(firstLine(e))});
        }
      }
    }
    rec.logs = logs.slice();
    // progress line the Python side can show live
    console.log(`tested ${sc.id}`);
  }

  await browser.close({silent: true});
  report.ok = true;
} catch (e) {
  report.error = cleanMsg(firstLine(e));
  console.error('test render could not run: ' + report.error);
}
finish();
process.exit(report.ok ? 0 : 1);

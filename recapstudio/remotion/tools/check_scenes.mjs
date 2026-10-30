#!/usr/bin/env node
// Static check for generated scenes (gameplan 4b). Usage:  node tools/check_scenes.mjs <manifest.json>
//
//   manifest: {"out": "report.json", "handles": ["footage_a"],
//              "scenes": [{"id": "d_02", "file": "<absolute path of the staged .tsx>"}]}
//   report:   {"scenes": {"d_02": {"errors": [{"line": 3, "message": "..."}], "warnings": [...], "cost": "low", "hasDefault": true}}}
//
// It parses every scene with the real TypeScript compiler (so strings, comments and look-alike names are handled
// properly) and REJECTS scenes that: import anything but 'remotion' / 'react' / '@kit', use the network, the
// filesystem, eval / Function / dynamic import, DOM or timer globals, or clock / random sources that would make
// frames differ between renders. kit/2 adds one rule: an `asset` attribute must be a plain literal naming a handle
// the step declared (`handles`), so a scene can neither spell a path nor name footage the run did not stage.
// A scene with errors is never bundled or run.
//
// Honest limits: this catches mistakes and obvious hazards in code an AI wrote. It is not a hardened sandbox.
// The scene still only ever runs inside the headless browser Remotion renders with, never with Node access,
// but read code you did not write before trusting it.

import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const rdir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const manifest = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

const ALLOWED_MODULES = new Set(['remotion', 'react', '@kit']);

// named exports of 'remotion' that load outside files, play sound or can hang a render
const BANNED_REMOTION = {
  Audio: 'plays sound (sound effects come from the SFX system, not from scenes)',
  Html5Audio: 'plays sound',
  Video: 'loads video files',
  Html5Video: 'loads video files',
  OffthreadVideo: 'loads video files',
  Img: 'loads image files (draw with SVG / CSS instead)',
  IFrame: 'embeds another page',
  staticFile: 'reads project files',
  delayRender: 'can hang the render',
  continueRender: 'can hang the render',
  getInputProps: 'reads the render settings',
  prefetch: 'loads files',
  watchStaticFile: 'reads project files',
  Internals: 'is Remotion internals',
};

const GLOBALS = {
  // network
  fetch: 'network access',
  XMLHttpRequest: 'network access',
  WebSocket: 'network access',
  EventSource: 'network access',
  Worker: 'starting extra threads',
  SharedWorker: 'starting extra threads',
  importScripts: 'loading outside code',
  Image: 'loading images: use SVG / CSS',
  Audio: 'playing sound',
  // running code from text / escaping
  eval: 'running code from text',
  Function: 'running code from text',
  require: 'loading modules',
  process: 'the Node.js process',
  globalThis: 'reaching global objects',
  window: 'the browser window',
  self: 'the browser window',
  top: 'the browser window',
  parent: 'the browser window',
  frames: 'the browser window',
  document: 'the page DOM: return React elements instead',
  navigator: 'browser information',
  location: 'the page address',
  history: 'the page history',
  localStorage: 'browser storage',
  sessionStorage: 'browser storage',
  indexedDB: 'browser storage',
  caches: 'browser storage',
  open: 'opening windows',
  alert: 'popups',
  confirm: 'popups',
  prompt: 'popups',
  postMessage: 'messaging other windows',
  BroadcastChannel: 'messaging other windows',
  MessageChannel: 'messaging other windows',
  WebAssembly: 'running native code',
  Proxy: 'intercepting objects',
  Reflect: 'reflection',
  // frame-by-frame rendering must be deterministic
  setTimeout: 'timers: animation must be driven by the frame number',
  setInterval: 'timers: animation must be driven by the frame number',
  setImmediate: 'timers: animation must be driven by the frame number',
  requestAnimationFrame: 'timers: animation must be driven by the frame number',
  cancelAnimationFrame: 'timers',
  queueMicrotask: 'timers',
  Date: 'the clock: use the frame number, frames render in parallel and must match',
  performance: 'the clock: use the frame number',
  crypto: 'random numbers: use random("seed") from remotion',
};

const BANNED_JSX = new Set(['script', 'iframe', 'object', 'embed', 'link', 'base', 'frame', 'frameset']);
const URL_RE = /(?:^|[^A-Za-z0-9])(?:https?:)?\/\/[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+|\bhttps?:\/\//i;

// kit/2 (M5.5B): an `asset` attribute names a handle the STEP declared (`"handles": [...]` in this
// manifest, which stdlib/scene_check.py fills from the step's `inputs.assets` keys). The same pattern
// the engine enforces on asset ids: a name, never a path.
const HANDLE_RE = /^[a-z][a-z0-9_]{0,31}$/;
const HANDLE_RULE = 'lowercase letters, digits and _ only, starting with a letter, at most 32 characters';
const handles = new Set(manifest.handles ?? []);

const FATAL_DIAG = new Set([
  2304, // Cannot find name
  2552, // Cannot find name ... Did you mean
  2305, // Module has no exported member
  2724, // Module has no exported member ... Did you mean
  2307, // Cannot find module
  2614, // Module has no exported member / default
  2459,
  2460,
]);

const compilerOptions = {
  target: ts.ScriptTarget.ES2018,
  module: ts.ModuleKind.CommonJS,
  moduleResolution: ts.ModuleResolutionKind.NodeJs,
  jsx: ts.JsxEmit.ReactJSX,
  strict: true,
  noEmit: true,
  skipLibCheck: true,
  esModuleInterop: true,
  baseUrl: rdir,
  paths: {'@kit': ['kit/index.ts']},
  types: [],
  lib: ['lib.es2020.d.ts', 'lib.dom.d.ts'],
};

const files = manifest.scenes.map((s) => s.file);
const program = ts.createProgram(files, compilerOptions);
const checker = program.getTypeChecker();

const isGlobalRef = (id) => {
  const sym = checker.getSymbolAtLocation(id);
  if (!sym) return true; // unresolved name: it can only be a global
  const decls = sym.declarations ?? [];
  if (!decls.length) return true;
  return decls.every((d) => program.isSourceFileDefaultLibrary(d.getSourceFile()));
};

const inTypePosition = (node) => {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isTypeNode(p) && !ts.isExpressionWithTypeArguments(p)) return true;
    if (ts.isStatement(p) || ts.isExpression(p)) return false;
  }
  return false;
};

const result = {scenes: {}};

for (const entry of manifest.scenes) {
  const errors = [];
  const warnings = [];
  const seen = new Set();
  const sf = program.getSourceFile(entry.file);
  const out = {errors, warnings, cost: null, hasDefault: false};
  result.scenes[entry.id] = out;
  if (!sf) {
    errors.push({line: 0, message: 'the scene file could not be read'});
    continue;
  }
  const lineOf = (node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
  const err = (node, message) => {
    const key = `${lineOf(node)}|${message}`;
    if (!seen.has(key)) {
      seen.add(key);
      errors.push({line: lineOf(node), message});
    }
  };
  const nsAliases = new Set(); // import * as R from 'remotion'
  const flaggedNames = new Set();

  const checkModule = (node, spec) => {
    if (!ALLOWED_MODULES.has(spec)) {
      err(node, `imports '${spec}', but scenes may only import from 'remotion', 'react' and '@kit'`);
      return false;
    }
    return true;
  };

  const visit = (node) => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const spec = node.moduleSpecifier.text;
      if (checkModule(node, spec) && spec === 'remotion' && node.importClause) {
        const nb = node.importClause.namedBindings;
        if (nb && ts.isNamedImports(nb)) {
          for (const el of nb.elements) {
            const name = (el.propertyName ?? el.name).text;
            if (BANNED_REMOTION[name]) err(el, `imports '${name}' from 'remotion', which ${BANNED_REMOTION[name]}`);
          }
        } else if (nb && ts.isNamespaceImport(nb)) {
          nsAliases.add(nb.name.text);
        }
      }
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
      checkModule(node, node.moduleSpecifier.text);
    } else if (ts.isImportEqualsDeclaration(node)) {
      err(node, "uses 'import x = require(...)'; use a normal import from 'remotion', 'react' or '@kit'");
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      err(node, "uses a dynamic import(); scenes may only use static imports from 'remotion', 'react' and '@kit'");
    } else if (ts.isPropertyAccessExpression(node)) {
      const n = node.name.text;
      if (n === 'constructor' || n === '__proto__') err(node, `uses .${n}, which can be used to run code from text`);
      if (ts.isIdentifier(node.expression) && nsAliases.has(node.expression.text) && BANNED_REMOTION[n]) {
        err(node, `uses remotion's '${n}', which ${BANNED_REMOTION[n]}`);
      }
    } else if (ts.isElementAccessExpression(node)) {
      const a = node.argumentExpression;
      if (a && (ts.isStringLiteral(a) || ts.isNoSubstitutionTemplateLiteral(a)) && (a.text === 'constructor' || a.text === '__proto__')) {
        err(node, `uses ['${a.text}'], which can be used to run code from text`);
      }
    } else if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName.getText(sf);
      if (BANNED_JSX.has(tag)) err(node, `uses the <${tag}> element, which loads outside content`);
    } else if (ts.isJsxAttribute(node) && node.name.getText(sf) === 'dangerouslySetInnerHTML') {
      err(node, 'uses dangerouslySetInnerHTML (return React elements instead)');
    } else if (ts.isJsxAttribute(node) && node.name.getText(sf) === 'asset') {
      // kit/2 (M5.5B): `asset` names a HANDLE the step declared - a plain literal, on a component.
      const host = node.parent && node.parent.parent;
      const tag = host && host.tagName ? host.tagName.getText(sf) : '';
      const init = node.initializer;
      if (!/^[A-Z]/.test(tag)) {
        err(node, `puts an 'asset' attribute on <${tag || 'an element'}>, which is not a component`);
      } else if (!init || !ts.isStringLiteral(init)) {
        err(node, `has a non-literal 'asset' (${init ? init.getText(sf) : 'no value'}): write asset="footage_a", a plain string literal naming a handle`);
      } else if (!HANDLE_RE.test(init.text)) {
        err(node, `has asset="${init.text}", which is not a handle: ${HANDLE_RULE} - never a path or a URL`);
      } else if (!handles.has(init.text)) {
        err(node, `uses asset="${init.text}", but this step declares no such handle`
          + (handles.size ? ` (declared: ${[...handles].join(', ')})` : '')
          + `: add "assets": {"${init.text}": "@asset.${init.text}"} to the step's inputs`);
      }
    } else if (ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) {
      if (URL_RE.test(node.text) && !(node.parent && ts.isImportDeclaration(node.parent))) {
        err(node, 'contains an internet address; scenes cannot load anything from outside (draw it with SVG / CSS)');
      }
      if (/@import\b/.test(node.text)) err(node, 'contains a CSS @import, which loads outside files');
    } else if (ts.isIdentifier(node)) {
      const parent = node.parent;
      const skip =
        (ts.isPropertyAccessExpression(parent) && parent.name === node) ||
        (ts.isPropertyAssignment(parent) && parent.name === node) ||
        (ts.isBindingElement(parent) && parent.propertyName === node) ||
        (ts.isJsxAttribute(parent) && parent.name === node) ||
        (ts.isPropertySignature(parent) && parent.name === node) ||
        (ts.isMethodDeclaration(parent) && parent.name === node) ||
        (ts.isQualifiedName(parent) && parent.right === node) ||
        ts.isJsxClosingElement(parent) ||
        inTypePosition(node);
      if (!skip && Object.prototype.hasOwnProperty.call(GLOBALS, node.text) && isGlobalRef(node)) {
        flaggedNames.add(node.text);
        const nm = node.text;
        err(node, `uses '${nm}' (${GLOBALS[nm]}), which scenes may not do`);
      } else if (!skip && node.text === 'Math' && ts.isPropertyAccessExpression(parent) && parent.expression === node && parent.name.text === 'random') {
        err(node, "uses Math.random(); frames render in parallel and must match, so use random('your-seed') from 'remotion'");
      }
    }

    // exports: default component + declared cost
    if (ts.isExportAssignment(node) && !node.isExportEquals) out.hasDefault = true;
    if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node)) && node.modifiers) {
      const k = node.modifiers.map((m) => m.kind);
      if (k.includes(ts.SyntaxKind.ExportKeyword) && k.includes(ts.SyntaxKind.DefaultKeyword)) out.hasDefault = true;
    }
    if (ts.isExportDeclaration(node) && node.exportClause && ts.isNamedExports(node.exportClause)) {
      for (const el of node.exportClause.elements) if (el.name.text === 'default') out.hasDefault = true;
    }
    if (ts.isVariableStatement(node) && node.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) {
      for (const d of node.declarationList.declarations) {
        if (ts.isIdentifier(d.name) && d.name.text === 'cost' && d.initializer && ts.isStringLiteralLike(d.initializer)) {
          out.cost = d.initializer.text;
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);

  // syntax errors first (the file may not even parse), then type problems
  const syn = program.getSyntacticDiagnostics(sf);
  for (const d of syn) {
    const line = d.start !== undefined ? sf.getLineAndCharacterOfPosition(d.start).line + 1 : 0;
    errors.push({line, message: 'syntax error: ' + ts.flattenDiagnosticMessageText(d.messageText, ' ')});
  }
  if (!syn.length) {
    for (const d of program.getSemanticDiagnostics(sf)) {
      const line = d.start !== undefined ? sf.getLineAndCharacterOfPosition(d.start).line + 1 : 0;
      const text = ts.flattenDiagnosticMessageText(d.messageText, ' ');
      const nameMatch = /Cannot find name '([^']+)'/.exec(text);
      if (nameMatch && flaggedNames.has(nameMatch[1])) continue; // already reported as a forbidden global
      if (d.code === 2307 && errors.some((e) => e.line === line)) continue; // already explained by the import rule
      if (FATAL_DIAG.has(d.code)) errors.push({line, message: text + ' (this would crash at render time)'});
      else if (warnings.length < 6) warnings.push({line, message: text});
    }
    if (!out.hasDefault) errors.push({line: 0, message: 'there is no default export: scenes must end with  export default MyScene;'});
    if (!out.cost) warnings.push({line: 0, message: "no `export const cost = 'low' | 'medium' | 'high'`; assuming 'medium'"});
    else if (!['low', 'medium', 'high'].includes(out.cost)) {
      errors.push({line: 0, message: `cost must be 'low', 'medium' or 'high', not '${out.cost}'`});
    }
  }
  errors.sort((a, b) => a.line - b.line);
}

fs.writeFileSync(manifest.out, JSON.stringify(result, null, 2));

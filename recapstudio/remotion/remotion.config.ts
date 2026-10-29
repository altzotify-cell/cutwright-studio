import path from 'path';
import {Config} from '@remotion/cli/config';

// jpeg frames render faster than png and the picture is opaque anyway.
// (A later transparent-overlay render will switch to png/prores per render.)
Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);

// Scenes import the helper kit as '@kit' (see kit/CONTRACT.md). tools/test_scenes.mjs repeats this alias.
// (process.cwd(), not __dirname: Remotion loads this file from inside its own CLI folder. Every launcher runs here.)
Config.overrideWebpackConfig((config) => ({
  ...config,
  resolve: {
    ...config.resolve,
    alias: {...(config.resolve?.alias ?? {}), '@kit': path.resolve(process.cwd(), 'kit')},
  },
}));

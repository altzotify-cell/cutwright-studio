import type {LabEntry, SceneMeta} from '../src/sceneTypes';
import type {Word} from '../kit';
import StatRing, {cost as statCost} from './stat_ring';
import TimelineReveal, {cost as timelineCost} from './timeline_reveal';
import QuoteMoment, {cost as quoteCost} from './quote_moment';
import MediaLayers, {cost as mediaCost} from './media_layers';

// The hand-written reference scenes. They are (1) previews in Remotion Studio ("example-..." compositions),
// (2) the patterns the scene-authoring prompt shows Claude (Phase 3), and (3) test material:
// "scenes --demo" copies them into a demo project so they go through the real check pipeline.

const FPS = 24;

// Narration stand-in for the preview: the words spread evenly over 85 % of the scene.
export const sampleWords = (text: string, durationInFrames: number): Word[] => {
  const toks = text.split(/\s+/).filter(Boolean);
  const span = durationInFrames * 0.85;
  return toks.map((w, i) => ({
    word: w,
    startFrame: Math.round((i / toks.length) * span),
    endFrame: Math.round(((i + 0.85) / toks.length) * span),
  }));
};

const make = (id: string, title: string, seconds: number, text: string, props: Record<string, unknown>, component: any, cost: any): LabEntry => {
  const durationInFrames = Math.round(seconds * FPS);
  const meta: SceneMeta = {
    id,
    title,
    cost,
    durationInFrames,
    fps: FPS,
    width: 1920,
    height: 1080,
    props,
    words: sampleWords(text, durationInFrames),
    text,
    status: 'example',
  };
  return {component, meta};
};

export const exampleScenes: Record<string, LabEntry> = {
  stat_ring: make(
    'stat_ring',
    'Stat ring',
    6,
    'Seventy percent of the players said the ending ruined the whole game for them.',
    {value: 70, label: 'of players disagreed', unit: '%', syncWord: 'seventy'},
    StatRing,
    statCost
  ),
  timeline_reveal: make(
    'timeline_reveal',
    'Timeline reveal',
    9,
    'It premiered in 1999, the sequel flopped in 2003, a cult following grew by 2010 and a remake was announced in 2021.',
    {
      events: [
        {when: '1999', label: 'The film premieres', word: 'premiered'},
        {when: '2003', label: 'The sequel flops', word: 'flopped'},
        {when: '2010', label: 'A cult following grows', word: 'cult'},
        {when: '2021', label: 'A remake is announced', word: 'remake'},
      ],
    },
    TimelineReveal,
    timelineCost
  ),
  quote_moment: make(
    'quote_moment',
    'Quote moment',
    7,
    'And then he said the line that everybody still remembers.',
    {quote: 'Every man dies. Not every man really lives.', author: 'Braveheart', highlight: ['lives']},
    QuoteMoment,
    quoteCost
  ),
  media_layers: make(
    'media_layers',
    'Media layers (footage + camera)',
    6,
    'The archive footage was found in a box, and nobody had seen it in twenty years.',
    {kicker: '1999', headline: 'The film nobody expected'},
    MediaLayers,
    mediaCost
  ),
};

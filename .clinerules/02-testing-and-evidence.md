# 02 - Testing and evidence

## No claims without output
Never claim something works without quoting the command output. `not_run` is not a pass.
"It compiles/imports/rendered" is not "it works/looks good".

## Test real outputs
- Produce the media, decode it, check frame counts/ids/audio, look at frames.
- Use short clips (5-20 s) - Remotion is ~5.7 fps here.
- Run the checks the milestone in `docs/ROADMAP.md` names, then record the result.

## Reporting format (use in every LOG entry and in every message to the owner)
```
TESTED     - <what> : <command> -> <quoted key result line(s)>
FAILED     - <what> : <command> -> <error text> ; <what you tried>
NOT TESTED - <what> : <why>
DECISIONS  - <what you chose, which assumption it relied on, how it was verified>
```

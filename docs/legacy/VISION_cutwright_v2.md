> **NOTE (2026-10-29).** Vision/direction only. Where this document names Shotcut as a backend, or cli-anything-shotcut, it is OVERRIDDEN by
> `docs/ARCHITECTURE.md` and `docs/ROADMAP.md`: Kinocut + FFmpeg are the editing infrastructure, Remotion the graphics renderer, Shotcut is removed.

# CUTWRIGHT V2 — MASTER DEVELOPMENT HANDOFF

## 1. Your Role

You are the lead software architect and implementation engineer for Cutwright, an agentic video-editing platform.

You are responsible for continuing the existing codebase, completing the current development roadmap, integrating new capabilities safely, and ultimately turning Cutwright into a reliable product usable by both AI agents and human creators.

You are not starting from scratch.

The repository already contains working code, documentation, tests, implementation decisions, safety restrictions, and existing handoff documents. Your first responsibility is to understand and preserve that work.

Do not replace working architecture simply because you prefer another approach.

## 2. Product Vision

Cutwright will become an agentic video-editing platform with five major components.

### A. Cutwright Core Engine

The engine is the foundation of the entire product.

It should eventually support:

- Video and audio inspection.
- Transcription and subtitle processing.
- Candidate-moment detection and frame verification.
- Intelligent edit planning.
- Timeline construction and clip arrangement.
- Titles, captions, transitions, overlays, and audio processing.
- Rendering and export.
- Automated validation of generated projects and rendered videos.
- Repeatable, recoverable editing workflows.

The engine must be usable independently of any particular AI provider or user interface.
## General-Purpose Video Creation and Professional Visual Quality

Cutwright is a general-purpose, AI-directed video creation platform. It is not limited to movie recaps, football videos, or any single genre.

Users must eventually be able to provide:

- Source videos and audio.
- A text prompt describing a video they want created.
- A script, article, transcript, or research material.
- Images, logos, datasets, and other creative assets.
- A combination of source material and creative instructions.

Cutwright should interpret the user's goal, select an appropriate production approach, create a Production Blueprint, generate or arrange the required visual material, render the video, and validate the result.

### Supported production categories

The architecture must accommodate multiple genres, including:

- Cinematic documentaries and recaps.
- Educational and scientific explainers.
- Professional motion graphics and kinetic typography.
- Data-driven visualizations.
- Product advertisements and promotional videos.
- Trailers, storytelling, and narrative sequences.
- Commentary and social-media videos.
- Music visualizers and experimental visuals.
- Tutorials, presentations, and screen-recorded demonstrations.
- Future genres without requiring a rewrite of the core engine.

These are intended capabilities. Do not claim a category is fully supported until its workflow has been implemented and tested.

### Production Blueprint

Before rendering a substantial video, the AI Director should create a structured Production Blueprint containing:

- Creative brief and intended audience.
- Genre and visual direction.
- Narrative structure and scene sequence.
- Duration, aspect ratio, frame rate, and resolution.
- Scene-by-scene timing and transitions.
- Required footage, generated assets, graphics, and visual effects.
- Typography, composition, color, lighting, and animation direction.
- Voiceover, music, sound effects, and audio-mixing requirements.
- Selected rendering backend and any specialized tools required.
- Validation criteria and known limitations.

The Blueprint must be independent of any specific rendering backend.

### Professional visual-quality requirement

Cutwright must not default to slideshow-style videos composed of static backgrounds, bullet points, and generic text animations.

For productions intended to look cinematic or professionally designed, prioritize:

- Deliberate visual storytelling and scene composition.
- Purposeful motion, transitions, timing, and pacing.
- Multi-layered graphics, dimensionality, and visual depth.
- Appropriate footage, illustrations, 3D scenes, or data visualizations.
- Consistent art direction, typography, lighting, and color.
- Professional sound design and balanced audio.
- Genre-appropriate visual techniques rather than one universal template.

Use static layouts when they genuinely serve the content, such as a chart, quotation, title, or intentionally restrained design. Do not introduce motion merely for decoration.

### Rendering architecture

Hyperframes should initially serve as a major backend for HTML/CSS/JavaScript-based motion graphics, animated scenes, and supported video compositions.

Retain the existing Shotcut backend for compatible timeline-editing workflows.

Evaluate additional backends or generative-media providers only when they fill a demonstrated capability gap. Do not add redundant dependencies merely to increase the number of technologies in the repository.

The architecture must distinguish between:

1. Editing and rendering existing source footage.
2. Creating motion graphics and procedural animation.
3. Generating new visual assets using generative-media systems.
4. Composing and finishing the complete video.

These capabilities have different dependencies, performance characteristics, and costs. The absence of a generative-media provider must not prevent locally supported editing and motion-graphics workflows.

### Quality assurance

Technical validity is necessary but insufficient.

Validation should cover both:

- **Technical correctness:** successful rendering, correct duration, media availability, audio integrity, resolution, frame rate, and other applicable output requirements.
- **Creative quality:** visual consistency, readable typography, appropriate pacing, coherent transitions, relevance of visuals, and compliance with the creative brief.

Automated quality checks should be supplemented by visual previews or sampled-frame review. Where creative quality cannot be reliably determined automatically, report the limitation and allow human review.

### Implementation policy

These capabilities describe the long-term product vision, not authorization to implement everything immediately.

Continue the existing milestone sequence. First stabilize the current core workflow, then integrate Hyperframes through the planned Phase 7. Schedule broader production workflows and professional-quality improvements as explicit, testable milestones.

Do not rewrite the engine, add multiple rendering frameworks, or introduce paid generative-media services before a concrete requirement justifies the change.

### B. AI Director

The AI Director is the orchestration and creative decision-making layer.

It should eventually be able to:

1. Interpret a user's creative brief.
2. Inspect source footage and available media.
3. Identify suitable moments using transcripts and actual visual evidence.
4. Construct a coherent edit plan.
5. Select suitable rendering and editing backends.
6. Generate the project and render the output.
7. Inspect validation results and relevant visual samples.
8. Correct problems and retry within defined limits.
9. Report what succeeded, what failed, and what requires human review.

The AI Director must not claim that an edit, render, or validation succeeded unless the result has actually been verified.

Creative quality and technical validity are separate concerns. Passing structural tests does not automatically mean a video is compelling.

### C. Agent Integration

Cutwright should be accessible to compatible AI agents through multiple integration mechanisms.

**Command-line interface (CLI)**

Provide predictable commands, actionable errors, machine-readable output where appropriate, and stable exit codes.

**Model Context Protocol (MCP)**

Eventually provide an MCP server that exposes documented Cutwright operations as tools for compatible AI clients.

Potential tools include video inspection, transcription, moment selection, edit-plan creation, project generation, rendering, and validation.

These are proposed capabilities, not assumptions that such tools already exist.

**Agent skill**

Provide a portable skill containing instructions, workflows, safety rules, command examples, and recovery procedures that teach compatible agents how to operate Cutwright correctly.

A skill provides instructions; the engine performs the actual work. MCP provides a standardized way for compatible agents to invoke available tools.

Do not implement MCP or a portable skill prematurely if the underlying operations are still unstable.

### D. Cutwright Studio

Cutwright should eventually provide a polished desktop application for human creators.

The intended workflow includes:

- Creating and managing projects.
- Importing footage.
- Reviewing transcripts and candidate moments.
- Previewing and editing AI-generated plans.
- Managing titles, captions, graphics, and audio.
- Monitoring renders and validation.
- Reviewing failures and correcting problems.
- Exporting deliverables or opening compatible projects in external editors.

The application must use the same underlying engine as the CLI and agent integrations.

Do not build a second, independent editing implementation inside the GUI.

Existing GUI code must be inspected before deciding whether to extend, refactor, or replace any part of it.

### E. Rendering Backends

Cutwright should support multiple backends behind a consistent internal interface.

**Shotcut**

Retain the existing Shotcut project-generation workflow and its validated capabilities. Shotcut remains a primary timeline-editing and project-compatibility target.

**Hyperframes**

Integrate Hyperframes as an additional motion-graphics and rendering backend, particularly for HTML/CSS-based compositions, animated titles, captions, lower thirds, statistics cards, and reusable visual overlays.

Hyperframes must complement the existing editing engine rather than replace the entire Cutwright architecture.

Future backends should be possible without rewriting the AI Director or the desktop application.

## 3. Mandatory First Step: Repository Reconnaissance

Before modifying any code:

1. Read `README.md`, `HANDOFF.md`, `HANDOFF_FULL.md`, `PROVENANCE.md`, `SKILL.md`, and other relevant project instructions that actually exist.
2. Inspect the repository tree, dependency configuration, CLI entry points, GUI implementation, core modules, tests, demo fixtures, and current Git state if available.
3. Identify implemented functionality, incomplete functionality, known failures, and existing safety restrictions.
4. Run the existing tests where the environment permits.
5. Inspect the current handoff's explicit next step and identify the exact implementation task currently authorized.
6. Compare documentation claims against actual code and test results.

Do not assume every document named above exists. Locate the actual files and inspect their contents.

Produce a concise assessment of:

- Current architecture.
- Verified working functionality.
- Known defects.
- Missing components.
- Existing roadmap and current milestone.
- Risks relevant to the next implementation task.

Do not spend the entire development session writing an assessment. Once the necessary reconnaissance is complete, begin implementation of the current authorized milestone.

## 4. Existing Handoffs and Roadmap Authority

The repository's existing handoff files contain the active implementation sequence.

Preserve that sequence unless the repository evidence demonstrates that a change is necessary.

The current handoff explicitly prioritizes the existing crossfade task and subsequent core milestones. The documented roadmap also includes provenance and read-only reconnaissance, coverage sheets, audio features, RecapStudio integration, optional integrations, and the complete editing pipeline.

The precise ordering and completion criteria must be recovered from the actual files rather than inferred from this summary.

Rules:

- Never skip the active milestone to implement a more exciting feature.
- Never silently reorder existing phases.
- Never mark a phase complete solely because code has been written.
- Preserve established safety invariants and existing test expectations.
- Update handoff documentation when a milestone is genuinely completed.
- If a task is blocked, document the evidence, blocker, and smallest useful next action.

This document defines the long-term product direction. It does not supersede the current implementation instructions in the existing handoffs.

## 5. Hyperframes Integration — Planned Phase 7

After the existing core roadmap is sufficiently complete and the end-to-end editing pipeline is stable, introduce a separate Phase 7 for Hyperframes.

Do not let this planned phase interrupt the currently authorized work.

### Phase 7A: Reconnaissance

- Verify the current Hyperframes project, official documentation, supported interfaces, installation requirements, and license.
- Determine the actual rendering workflow and available output formats.
- Verify compatibility with the existing Cutwright architecture and local environment.
- Record third-party provenance, licensing, and dependency decisions in `PROVENANCE.md`.
- Avoid assuming that undocumented commands, APIs, or features exist.

### Phase 7B: Minimal Proof of Concept

- Generate a small animated title composition.
- Render a short sample locally.
- Verify the output's dimensions, duration, frame rate, and render success.
- Investigate transparent video output for overlays where supported.
- Record the commands, dependencies, test results, and known limitations.

### Phase 7C: Integration

- Reuse Cutwright's existing editing-plan architecture wherever practical.
- Introduce a shared, versioned edit-plan representation only if the current architecture does not already provide an adequate one.
- Define a clean backend interface separating editing intent from backend-specific implementation.
- Implement a Hyperframes adapter for supported motion-graphics operations.
- Keep Shotcut-specific operations in the existing Shotcut backend.
- Ensure a Hyperframes failure does not unnecessarily break the Shotcut workflow.
- Avoid duplicating transcription, moment selection, validation, or AI orchestration logic.

### Phase 7D: Validation

- Add automated tests for composition generation and rendering.
- Verify timing, dimensions, media existence, and alpha transparency when relevant.
- Test failure handling and missing dependencies.
- Confirm that existing tests continue to pass.
- Document the features actually verified and those still incomplete.

The first Hyperframes milestone should be deliberately small: one animated title and one usable overlay. Expand only after the proof of concept works reliably.

## 6. Development Principles

### Preserve existing work

- Make incremental changes.
- Reuse existing modules where appropriate.
- Avoid unnecessary rewrites.
- Keep changes scoped to the current milestone.
- Do not delete existing functionality without clear justification and appropriate tests.

### Validate claims

- Inspect actual code before documenting functionality.
- Run relevant tests after modifications.
- Distinguish passing tests from tests that could not run.
- Never fabricate test results.
- Verify rendered outputs when a task concerns rendering.
- Distinguish technical validation from subjective creative quality.

### Control costs

Prefer free, local, and open-source tools where practical.

For AI-assisted development, use inexpensive models for routine implementation and reserve more capable models for difficult architectural decisions or debugging.

Reduce unnecessary token usage by:

- Reading relevant files before requesting large repository summaries.
- Making focused changes.
- Reusing test fixtures.
- Avoiding repeated full-file rewrites.
- Using deterministic scripts for deterministic operations.
- Running targeted tests before the full suite when appropriate.

Do not introduce a paid API dependency into a workflow that can reasonably operate locally without one.

### Safety and recovery

Preserve the repository's existing workspace boundaries and write restrictions.

Do not modify original source media or unrelated projects.

Avoid destructive operations, unsafe path handling, and uncontrolled recursive writes.

Use temporary outputs and atomic writes where appropriate.

Keep failed operations diagnosable and recoverable.

### Documentation

Update documentation to reflect actual behavior, not intended future behavior.

Record relevant changes in the handoff and provenance documents.

Do not claim that MCP, the desktop application, a skill, or a backend is complete merely because a directory, class, or placeholder exists.

## 7. Definition of Done

A feature is complete only when its applicable acceptance criteria are satisfied.

These may include:

- Implementation exists.
- Interfaces and inputs are documented.
- Relevant tests pass.
- Existing functionality remains intact.
- Failure cases are handled.
- Output artifacts are verified.
- Provenance and dependency documentation are updated.
- Known limitations are explicitly recorded.

A feature that has been implemented but not adequately tested must be reported as implemented but unverified.

## 8. Required Development Handoff After Every Milestone

At the end of each implementation session, provide a concise report containing:

1. **Completed:** Exact files and behaviors implemented.
2. **Tests:** Commands run and actual results.
3. **Unverified:** Anything not successfully tested.
4. **Outstanding:** Remaining work and known blockers.
5. **Documentation:** Handoff, README, or provenance changes.
6. **Next action:** The smallest concrete next implementation task.

Update the appropriate handoff file so another coding session can continue without rediscovering the entire repository.

Do not claim the whole product is complete when only a milestone is complete.

## 9. Long-Term Completion Criteria

Cutwright's full product vision is achieved when:

- The core engine can reliably execute a complete editing workflow.
- The AI Director can plan, execute, inspect, and recover from supported editing failures.
- Shotcut and Hyperframes operate as compatible, independently testable backends.
- A compatible AI agent can control Cutwright through a documented MCP interface.
- A portable agent skill teaches supported agents how to use Cutwright.
- Cutwright Studio provides a usable human interface to the same engine.
- The complete workflow has reproducible tests and verified output artifacts.
- Installation, configuration, dependency handling, and limitations are documented.
- Human users can review and override creative decisions rather than being forced to trust an opaque automation process.

These are long-term objectives, not claims about the current repository.

## 10. Immediate Instruction

After reading this document, return to the repository's existing handoff instructions.

Identify the active milestone, inspect its acceptance criteria, and implement that milestone.

Do not start Phase 7 merely because it is described here.

Do not attempt to build the engine, MCP server, skill, desktop application, and every backend simultaneously.

Work incrementally, preserve existing functionality, verify the results, and maintain an accurate handoff for the next session.
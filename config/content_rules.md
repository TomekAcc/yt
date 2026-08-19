# Content Rules — "The Ledger"

This file is the single source of truth for how every video on this
channel is written, illustrated, and paced. **Edit this file to change the
rules** — the pipeline reads it automatically on every run (`_handle_scripting`
in `yt_engine/pipeline.py` loads it and feeds it straight into the
script-writing prompt), so a wording change here changes the next video
with no code edits or redeploy needed.

## 1. Script Writing Rules

**Entertaining, not encyclopedic.** Write for a viewer who clicks away in
seconds if bored.

- Open with the single most dramatic, surprising, or high-stakes moment of
  the story as a cold-open hook — never with background or context first.
- Use concrete, specific, sensory details: names, exact numbers, places,
  what someone actually said or did. Never abstract summary ("the company
  struggled financially") when a specific fact is available ("the company
  had eleven days of cash left").
- Build tension scene to scene. Every scene should make the viewer want
  the next one — end scenes on a question, a turn, or a consequence, not
  a flat statement.
- Vary sentence rhythm. Mix short punchy sentences with longer ones. Never
  use textbook phrasing: banned phrases include "it is important to note,"
  "this was significant because," "in conclusion," "as we can see."
- End on a sharp final thought or irony, never a fade-out summary
  ("and that's the story of...").

**100% factually accurate — no exceptions.**

- Every claim, number, date, name, and quote must come directly from the
  research brief's key facts or timeline. Never invent, round dramatically,
  or embellish a fact to make it more exciting — the true story is dramatic
  enough on its own.
- If a specific detail isn't in the research (an exact quote, a precise
  figure), either omit it or phrase the sentence so it doesn't require it.
  Never fabricate a specific to fill a gap.
- When a fact is disputed or uncertain in the historical record, say so
  ("some accounts say...") rather than presenting it as settled.

**Structure:** cold open hook → setup → rising conflict → climax →
resolution → closing thought. No dialogue, no "picture this," no filler.
Written in complete sentences meant to be read aloud by a calm, confident
narrator.

## 2. Visual Style Rules

The detailed, era-aware art direction (color palette, composition,
recurring motifs, negative prompts) lives in
`config/style_guides/financial_history.yaml` and is injected into every
single image prompt automatically — that file is what actually keeps every
video's imagery consistent, so edit it (not this section) to change the
art style itself.

The rules that govern *how that style guide gets used*:

- Every image prompt must explicitly follow the active style guide's
  `art_style` and era-appropriate `palette_by_era` entry — never default to
  a generic or inconsistent look for a scene.
- No on-image text, numerals, or watermarks (rendered separately as
  subtitles instead — mixing AI-generated text into the image itself
  produces garbled, unprofessional results).
- Favor symbolic and environmental shots (ledgers, skylines, telegrams,
  stock tickers, empty offices) over literal photorealistic portraits of
  named individuals, per the style guide's `composition_rules`.
- Each scene's image must depict what that scene's narration is actually
  about — never a generic "stock photo" filler image unconnected to the
  specific moment being narrated.

## 3. Pacing & Motion Rules

The tunable numbers live in `config/settings.yaml` under `video:` — this
section documents *why* they're set that way, so future adjustments have a
rationale to check against:

- **Scene length** (`scene_max_duration_sec`): images should change often
  enough that the video never feels static. 12 seconds per image is the
  current target — if it still feels slow, lower this further before
  changing anything else.
- **Motion** (`ken_burns_zoom_range`): every held image should visibly
  drift/zoom the whole time it's on screen, never sit perfectly still.
- **Subtitles** (`subtitle_margin_v`): positioned low enough to feel like a
  normal caption bar, not so high that it overlaps the main image content.
- Pan direction should rotate across scenes (center / left-to-right /
  right-to-left / top-to-bottom) rather than repeating the same motion
  every time — this is handled automatically by the video assembler.

## 4. Voice & Narration Rules

- One consistent narrator voice/tone across every video on the channel
  (set via `providers.tts_voice` in `config/settings.yaml`) — never switch
  voices between videos.
- Calm, confident, measured documentary delivery — not hyped or
  sensationalized, even when the story itself is dramatic. The drama
  should come from the writing and facts, not vocal exaggeration.
- Narration pacing should match natural spoken rhythm (~150 words/minute)
  — sentences are written to be read aloud, not skimmed.

## 5. Consistency Mandate

Every video on this channel must feel like it belongs to the same show:
same narrator voice, same art style, same pacing rules, same title/caption
formatting, same intro energy. Sub-format rotates (company case study /
currency crisis / wealth biography / economic era, per STRATEGY.md §1) but
the *treatment* — how it looks, sounds, and paces — never varies between
videos. If a change is wanted, it belongs in this file (or the linked
style guide / settings), applied to every future video at once, not
adjusted ad hoc per video.

## 6. Compliance Rules

Full rationale in `STRATEGY.md` §5. Summary: every script must be
multi-sourced, every video must disclose synthetic media, sub-formats must
rotate, and by default a human reviews and approves the script before any
image/voice generation begins. These are enforced automatically by
`yt_engine/content/compliance.py`, not just documented here.

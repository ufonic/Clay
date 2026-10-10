# Labeling your takes (task 0.6)

Your hand-checked notes are the answer key Clay's note detection is graded against (the Phase 1 gate: note F1 ≥ 0.95 on these takes). Five takes, roughly 15–30 minutes each.

## 1. Pick and copy the takes

- About 12 **dry** lead-vocal takes (no reverb, delay, or tuning), mono or stereo WAV, any sample rate.
- Choose 5 to label that cover different things: a slow ballad, something fast, a take with vibrato, one with slides, one with breathy or quiet parts.
- Copy them into `data/owner_takes/` in the Clay folder. Use simple file names (letters, numbers, `-`, `_`), e.g. `ballad-verse.wav`.

## 2. Start the labeler

In a terminal in the Clay folder:

```
uv run --project research python -m clay_research.labeling.server
```

Your browser opens at http://127.0.0.1:8765. The first time you open a long take it analyses the pitch, which can take up to a minute. Leave the terminal open while you work; press Ctrl+C there when done.

## 3. Correct the notes

Each take opens with a **first guess** (blue boxes) over the pitch curve (grey line). The guess deliberately over-splits slides and scoops: your job is to make the boxes match **the notes you meant to sing**.

| To… | Do this |
|---|---|
| Hear it | `Space` plays from the red cursor; click empty space to move the cursor |
| Check your labels by ear | **Guide tones** plays your boxes as tones over the vocal |
| Fix a wrong pitch | Drag the box up/down, or select it and press `↑` / `↓` |
| Fix where a note starts/ends | Drag the box's left/right edge |
| Merge pieces of one note | Select the first piece, press `J` |
| Split one box into two notes | Put the cursor inside it, select it, press `S` |
| Add a missed note | Double-click where it should be |
| Remove a non-note (breath, click, consonant) | Select it, press `Delete` |
| Undo | `Ctrl+Z` |
| Move around | Mouse wheel scrolls · `Ctrl`+wheel zooms · `Shift`+wheel scrolls pitch · click the strip at the bottom to jump |

**Rules of thumb**
- A scoop or slide into a note belongs to that note: the box starts where the note starts, at the pitch you were aiming for.
- Vibrato is one note.
- A note starts at its attack (the consonant before it doesn't count) and ends where the sound stops or the next note begins.
- If you sang slightly flat or sharp, label the note you **intended** (that's what tuning will aim for).
- When unsure, play it with Guide tones on and trust your ear.

## 4. Save

- **Save draft** (`Ctrl+S`) any time. Drafts don't count toward scores.
- **Save & mark verified** when the take is finished.
- Labels are saved to `research/labels/owner/<take>.json`. They're committed to git (they're small and precious); the audio never is.

When five takes say "✓ verified", tell Claude "takes labeled".

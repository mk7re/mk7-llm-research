# Reviewed research

Index of the documents about Mario Kart 7 (`eur2`) that a human has reviewed and accepted, one folder per subject in
`docs/research/<topic>/`. When starting a task, look through this index and read only the documents relevant to it.
They are a good source, but not infallible: when one disagrees with `eur2`, `eur2` wins.

## Contents

- [Rules](#rules): what may be added here, and by whom
- [Index](#index): one row per subject

## Rules

- Only human-reviewed documents live in `docs/research/`. They arrive from `final/` once a human has approved them;
  the agent does not add to this folder or to this index on its own
  ([Human review](../tooling/WORKFLOW.md#human-review)).
- One folder per subject, each with one row in the index below: a link and a phrase saying what it explains, precise
  enough to decide whether to read it.

## Index

| Subject | Description |
| --- | --- |
| [Scene and menu sequencing (BSEQ: `.brs` / `.bss`)](scene-sequence-bseq/README.md) | how the game handles its scenes and menus, driven by the BSEQ files (`.brs` / `.bss`) in `UI/common.szs`: the full file format, section names and IDs, enter and return codes, modes, how the code builds a flow from a file, unused debug leftovers, rules for editing the files, and a tool that draws the whole flow as one image |
| [Ghost checkpoints (checkpoint search and respawn glitches)](ghost-checkpoints/README.md) | how the game finds a kart's checkpoint from the KMP checkpoints (CKPT / CKPH): the quad test, the search and its gap bridging, which results become the current checkpoint and how that picks the respawn point; why the search can return far-away "ghost" checkpoints that cause respawn glitches, the Wuhu Loop shortcut, what v1.1 changed online (code and patched KMPs), places worth checking on other courses, and a tool that draws the ghost checkpoints of any course |

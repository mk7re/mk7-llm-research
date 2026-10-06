# Documenting the tooling

Rules for anyone, agent or human, who changes the tooling (`mk7`, `tools/mk7re`) or the workspace documentation
(`README.md`, `docs/tooling/`). The goal is documentation that an agent can route through cheaply: it reads a
table of contents, picks the sections or subdocuments its task needs, and skips the rest. Topic documents of
research follow [WRITING.md](WRITING.md) instead.

## Contents

- [Where documents live](#where-documents-live): the router, `docs/tooling/`, `docs/research/`
- [Every document](#every-document): opening lines and table of contents
- [Main documents and subdocuments](#main-documents-and-subdocuments): when to split, how to link
- [Examples and measurements](#examples-and-measurements): only in subdocuments, in sections of their own
- [Argument tables](#argument-tables): every argument of every command, described
- [Shared-project rule](#shared-project-rule): no facts about one person's setup
- [Checklist for a tooling change](#checklist-for-a-tooling-change)

## Where documents live

- `mk7-llm-research/README.md` is the router: the workspace rules and a document map with one "read it when" phrase per
  document, including the index of reviewed research. It holds no tool documentation itself. A new document gets a row
  in its document map.
- `docs/tooling/` holds the workspace's own documentation: setup, the CLI, the emulator, game data, the research
  workflow and these rules. Subdocuments go into a subfolder named after their main document (`cli/`, `emulator/`).
- `docs/research/<topic>/` holds human-reviewed research only ([WORKFLOW.md](WORKFLOW.md#human-review)); its index is
  [docs/research/INDEX.md](../research/INDEX.md), one line per subject.
- No documents at the top of `mk7-llm-research/` other than `README.md`.

## Every document

- It opens with a title and one to three lines that say what it covers and, for a subdocument, which main document
  it belongs to and when to read it.
- A `## Contents` list follows at once: one line per `##` section, a link to its anchor and a short phrase that says
  what is in it, precise enough to decide whether to read it. The title, the opening lines and the contents fit in
  the first 30 lines, so that `head -30` is enough to route.
- The contents list is updated in the same change as the sections it lists.
- Links between documents use relative paths and anchors (`[Code pages](emulator/hooks.md#code-pages)`), so that a
  reader can jump to the one section it needs. After moving or renaming a section, check the links to it.
- Research is named by its subject, never linked and never by its folder name: "the research on scene and menu
  sequencing (BSEQ), Finding 13 (How button controls complete pages)". A topic moves from `pending-verification/` to
  `final/` to `docs/research/`, and its folder may be renamed, so a link, a path or a folder name would go stale; the
  reader finds the topic from its subject in those folders or in [docs/research/INDEX.md](../research/INDEX.md). The
  same holds for the tooling's code and output (`mk7 kmp fields` names its sources by subject).

## Main documents and subdocuments

- A main document is a file directly in `docs/tooling/`. It says what something is for, the rules for using it, and
  where the details are. It stays short; when a section grows into details that only some tasks need (an algorithm,
  internals, long tables), that section moves into a subdocument.
- A main document lists its subdocuments in a table with a "Read it when" column: one phrase per subdocument that lets
  an agent decide, without opening it, whether it needs it.
- A subdocument covers one subject and links back to its main document in its opening lines.
- Facts live in one place. Another document links to that place instead of repeating the fact; a short rule may be
  repeated in a main document when it is a constraint every reader must respect (with the link to the details).

## Examples and measurements

- Main documents hold no use examples, no measured figures (timings, sizes, memory, frame rates, counts that change
  when a tool or table changes) and no dated observations. They state the rule or the behaviour; the evidence is
  elsewhere.
- Subdocuments may keep examples and measurements where they help, in sections of their own at the end:
  `## Use examples` for commands or scripts, `## Measurements` for figures and dated observations. The contents list
  marks them, so an agent can skip them. In the body, link to them rather than quoting the figures
  (`([Measurements](#boot-frames))`).
- A number that is part of the behaviour (a default, a threshold the code uses, an address, a table of values the game
  uses) is not a measurement and stays in the body.

## Argument tables

- Every command of `mk7` has a section in a `docs/tooling/cli/<group>.md` file: a heading with its synopsis, one
  sentence on what it does, and a table `| Argument | Description |`.
- The table covers **every** argument the parser accepts, positional and optional, with its short and long spelling.
  A command without arguments says "No arguments."
- Each description says what the argument does, what values it takes (choices, units, number format) and its default.
  It is written for a user who has not read the code: no "see code", no bare restatement of the option name.
- Conventions stay inside one file. A `cli/<group>.md` file may define once, in a `## Conventions` section at its
  top, what many of its own commands share (a number format, an option group such as the driver options of
  `mk7 emu`, an argument syntax such as `COURSE`), as long as the convention holds for every command of that file
  that uses it. Each table row that relies on a convention links to it. A convention never reaches into another file:
  a target syntax, an image option or the global `--templates DIR` is described in the table of every command it
  applies to, whichever file that command is in, never in a conventions section of another document (CLI.md has
  none).
- An argument the parser accepts but the command ignores is listed and says so.
- When a command or argument is added, removed or changed in the code, its table changes in the same step, and so does
  the argparse `help` text. Compare the tables with the parser (`mk7 <command> --help`) after the change.

## Shared-project rule

This is a shared project: everything committed is written for anyone who clones it. The documents hold no facts about
one person's setup: no machine specs, local paths beyond the documented defaults and variables, personal incidents or
preferences. Write such a fact as a general rule, or keep it in the agent's own memory or in a `local` folder.

## Checklist for a tooling change

1. The argument tables in `docs/tooling/cli/` match the parser.
2. Behaviour that changed is updated in the one document that holds it; main documents only if a rule or the routing
   changed.
3. New measurements or examples went into a subdocument's `## Measurements` or `## Use examples`.
4. Contents lists, "Read it when" phrases and the router's document map still describe what the files hold.
5. Links to moved or renamed sections still resolve.

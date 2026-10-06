# Writing a topic document

Rules for the `README.md` of a research topic. Pass 1 writes it, pass 3 checks it against these rules
([WORKFLOW.md](WORKFLOW.md)).

## Contents

- [Structure](#structure): the sections of a topic document and its two parts ([overview](#part-1-the-overview),
  [technical details](#part-2-the-technical-details))
- [Headings](#headings): headings instead of bold-titled paragraphs
- [Wording](#wording): one term per thing, ideas introduced before use
- [Glossary and naming](#glossary-and-naming): referring to members, functions, enums and data; final names; the
  glossary tables

## Structure

```
# <Topic>

- Status: pending verification
- Asked: <the user's question, as asked>
- Base commit: <git rev-parse HEAD that the patches apply on; updated with them (PATCHES.md)>
- Images: <images used, with sha1 for the target>

## Overview           part 1: what was researched and found, for readers new
                      to the topic
## Glossary           part 2 starts here: the classes, members, functions and
                      data involved, with their offsets and addresses
## Findings           each claim with its evidence: the function, and the
                      instruction or decompiled line that shows it
## Confidence         what is certain, what is likely, what is a guess
## Open questions     what was not resolved
## Patches            each .patch file and what it changes
## How to verify      the commands that reproduce the key evidence
## Review             added by passes 2 and 3
```

The sections come in this order, and similar content is laid out the same way in every section. The document has two
parts, written for two different readers.

### Part 1: the overview

`## Overview` is written for someone who plays the game and knows some programming, but has never looked at its code. It
explains what is being researched and what it does in the game, how it works, and what was found. Practical advice for
the people the question is about (course creators, modders, players) belongs here too.

- It opens with what was found, in a few lines, before going into detail.
- Common programming terms and simple math are fine: arrays, lists, flags, bits, state machines; distances, angles,
  vectors, averages, probabilities, a short formula. Pseudo-code, long derivations, and anything that needs knowledge of
  the engine are not.
- No addresses, no memory offsets, no decompiled code or instructions. Offsets inside a game file are fine where the
  reader needs them to edit that file.
- Code names are kept to a minimum. A thing is described by what it does; when its name helps the reader find it in part
  2, the name follows the description.
- The overview makes no claim of its own. Every statement in it is backed by a finding in part 2, links to it, and keeps
  the certainty that `## Confidence` gives it ("probably", "not tested in game").

### Part 2: the technical details

The sections from `## Glossary` on are written for someone who will check the research or build on it: names, offsets,
conditions on variables, algorithms, constants, call order, and the evidence for each.

- Every claim cites evidence in `eur2`. A claim that rests only on `dlp` or an older build says so and counts as
  unconfirmed.
- Addresses appear only in the glossary. The evidence names the function and quotes the instruction or decompiled line;
  the reader looks the address up in the glossary. The one exception is `## How to verify`, whose commands use an
  address only where the CLI needs one: existing names are accepted (`mk7 decomp Field::MapdataEnemyPoint::setup`),
  names given by the research are not in the symbol maps yet.

## Headings

In both parts, structure is given by headings, not by bold text. A series of paragraphs that forms a self-contained idea
or topic (one mechanism, one block of a file format, one kind of object) gets its own subsection (`###`), or a
sub-subsection (`####`) when it is part of a subsection. A paragraph that opens with a bold title (`**Quads.** A
checkpoint and ...`) is a heading in disguise and is written as a heading instead. Bold is kept for emphasis inside a
sentence. A section that holds a single short idea needs no subsections.

## Wording

- Each term means one thing, and each thing is called by one term throughout the document.
- Words that could be read in more than one way (a game term that is also a class name, "point", "index", "entry", ...)
  are replaced or qualified so the reader cannot confuse them.
- Ideas are introduced before they are used. The reader may not read the glossary first, so it does not count as an
  introduction: a class, function, concept or new idea is presented in the text, in a few words, before any sentence
  relies on it. The overview does not rely on part 2 for this.

## Glossary and naming

Part 2 starts with the glossary, so that all documents read the same way and every name has one place that lists its
offset or address, type and status. It comes after the overview so that a reader new to the topic meets the explanation
first, not a table of offsets.

- **Members are referred to by name, never by offset.** Write `EnemyPoint::m_next_count`, not `EnemyPoint+0x2C`. The
  offset appears once, in the glossary.
- **Members are written as `Class::member`.** A bare member name (`m_next_count`) is allowed only where it is beyond
  doubt which class it belongs to, such as a row of the glossary table of that class.
- **Use the existing name** when `template/` already has one.
- **Give a name to anything that has none** (a gap, or an unnamed `/U/` member) before writing about it, following the
  conventions of the surrounding templates (`m_snake_case`). Pick the name from what the evidence shows the member does.
  If its purpose is still unclear, name it after what the evidence does show, never after its offset.
- **Names are final.** No name is marked provisional, in the document or in the patch. Pass 2 may rename what the
  evidence contradicts and pass 3 may rename what reads badly; after pass 3 the names stay as they are unless the human
  changes them. What is not understood about a member goes into `## Open questions`, not into its name.
- **Members that hold a state, kind or mode get an enum**, declared in their class and holding only the known values
  ([Enums](PATCHES.md#enums)). An enum that has no name in the symbols or the game is given one, like a member.
- **New names go into the patch**, so that the documentation and the templates end up with the same names once the human
  applies it. A document that introduces names therefore comes with a `.patch`.
- **Where a member is set, read or tested is written here, not in the patch.** The template comments are for
  programmers using the class ([Comments](PATCHES.md#comments)); the Note column and the findings say which functions
  use the member.
- List only the classes and members the document talks about, not whole layouts.
- Offsets in the glossary are relative to the start of the class that the table is about, and are those of `eur2`.

One table per class:

```
## Glossary

### Field::EnemyPoint (size 0x48, template/Field/Entry/EnemyPoint.hpp)

One line on what the class is.

| Member | Offset | Type | Status | Note |
| --- | --- | --- | --- | --- |
| `m_position` | 0x00 | `sead::Vector3f` | existing | |
| `m_next_count` | 0x2C | `u8` | new | number of valid entries in `m_next` |
| `m_route_flags` | 0x30 | `u32` | new | bit 0 tested in `calcRoute`; the other bits are an open question |
| `m_kind` | 0x34 | `EKind` | new | was `u8`; set by `setup` from the KMP setting |

#### Field::EnemyPoint::EKind (enum class : u8)

New; named by this research.

| Value | Name | Status | Note |
| --- | --- | --- | --- |
| 0 | `NORMAL` | new | |
| 2 | `DRIFT` | new | CPUs start a drift here |
```

Status is `existing` (already named in `template/`), `renamed` (the patch changes an existing name; give the old one in
the note) or `new` (named by this research, added by the patch). A member whose type the patch changes to an enum says so
in its note, with the old type.

An enum the document talks about has a table of its own, under the table of the class that declares it. Its heading
gives the full name and the base type; the line below says whether it is new or existing and, for a new one, whether
the name comes from the symbols or the game (and from what) or was given by this research. The table lists the values
the patch declares.

Functions are referred to by name too. A function that has no name in `eur2` is given one. Every function the text
refers to is listed with its `eur2` address in a `### Functions` table at the end of the glossary (`Name | Address
(eur2) | Status | Note`). Names ported from `dlp` count as existing.

Data the text refers to (a table, a global, a vtable) is named the same way and listed in a `### Data` table after the
functions (`Name | Address (eur2) | Note`). A constant that a function loads (`vldr s0, =150f`) is cited by its value
and the function that loads it, without an address.

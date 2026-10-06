# Research workflow

The environment exists to understand the game better. A research task asked by the user can end in new or improved
templates, in a written explanation, or in both. Whatever the result, it goes through three passes by the agent and a
final review by a human. Each pass starts with a context reset, and the agent stops and reports at the end of each one;
nothing is moved or committed beyond what the pass says.

## Contents

- [The passes](#the-passes): who does what, from what status to what status
- [Pass 1: research](#pass-1-research): checking what is known, investigating, writing to `pending-verification/`
- [Pass 2: fact check](#pass-2-fact-check): re-checking every claim and patch against `eur2`
- [Pass 3: document review](#pass-3-document-review): checking the document against [WRITING.md](WRITING.md)
- [Human review](#human-review): what the human does with `final/`
- [The three folders](#the-three-folders): `pending-verification/`, `final/`, `docs/research/` and how far to trust each

## The passes

| Pass | Done by | Starts from | Ends with |
| --- | --- | --- | --- |
| 1. Research | agent, fresh context | the user's question | `pending-verification/<topic>/`, `Status: pending verification` |
| 2. Fact check | agent, fresh context | `Status: pending verification` | `Status: facts checked` |
| 3. Document review | agent, fresh context | `Status: facts checked` | `final/<topic>/`, `Status: verified` |
| Human review | human | `final/<topic>/` | patches applied, document moved to `docs/research/` |

## Pass 1: research

The user starts the research in a fresh context. The agent:

1. Checks what is already known about the topic, without reading everything: it looks through the [index of reviewed
   research](../research/INDEX.md) and the topic names in `final/`, and reads only the documents that are relevant to
   the question. The topic names in `pending-verification/` only show work already under way; their content is not used
   ([The three folders](#the-three-folders)). A relevant document of `docs/research/` is a good source, but it may not
   be fully accurate: `eur2` always wins. Where the two disagree, the agent says so in the topic document and in its
   report, so that the human can correct `docs/research/`.
2. Investigates in `eur2` (`mk7 struct`, `gaps`, `access`, `dis`, `decomp`, `xref`, ...), using the other builds as
   references.
3. Writes the results to `pending-verification/<topic>/`, where `<topic>` is a short lowercase name with dashes
   (`kart-unit-layout`, `item-probability`):
   - `README.md`, always, following [WRITING.md](WRITING.md).
   - `REVIEW.md`, always, with the `## How to verify` section ([The review document](WRITING.md#the-review-document)).
   - `*.patch` files, when the research changes `template/` ([PATCHES.md](PATCHES.md)).
4. Stops and reports.

## Pass 2: fact check

The user resets the context, so the reviewer has not seen how the conclusions were reached, and asks for the facts of
the topic to be checked. The reviewer:

1. Reads `pending-verification/<topic>/` and treats it as claims to test, not as facts. This includes the glossary:
   offsets, types, addresses, the values of each enum, and whether each new name fits what the member, function or enum
   value does. A name the evidence contradicts is changed, in the document and in the patch.
2. Re-checks every finding against `eur2` independently, and checks that each patch still applies (`git apply --check`)
   and that `mk7 --templates ... verify` passes on a fresh work copy with the patch applied to it. A patch that fails
   only because `template/` changed after its base commit is updated, and does not count against the research ([When
   the base commit has moved on](PATCHES.md#when-the-base-commit-has-moved-on)).
3. Checks that the document agrees with itself and with the evidence:
   - Names, offsets, addresses, values and conclusions are the same wherever they appear, and no section contradicts
     another.
   - Every statement of the overview is backed by a finding, with the certainty that `## Confidence` gives it. A
     statement that has no finding behind it is either supported with one or removed.
4. Corrects what is wrong and removes what cannot be supported. It rewrites only what a correction needs; style, wording
   and structure are left to pass 3.
5. Adds a `### Fact check` subsection to the `## Review` section of `REVIEW.md` (creating the section if it is not
   there yet): what was re-checked and how, what was changed, what remains uncertain.
6. If the research holds, sets `Status: facts checked` and leaves the folder in `pending-verification/`. If it does not
   hold, leaves the status as it is, with the review explaining why.
7. Stops and reports.

## Pass 3: document review

The user resets the context again, so the reviewer reads the document the way its readers will, without knowing the
evidence behind it, and asks for the document of the topic to be reviewed. Only a topic with `Status: facts checked` is
reviewed. The reviewer reads [WRITING.md](WRITING.md) and goes through the topic `README.md` section by section, then
through `REVIEW.md` and the patches, checking:

1. **Structure**: the sections, their order, and similar content laid out the same way everywhere
   ([Structure](WRITING.md#structure)); no section on the patches, and the commands and the reviews in `REVIEW.md`, not
   in `README.md` ([The review document](WRITING.md#the-review-document)); one heading per self-contained idea, no
   bold-titled paragraphs ([Headings](WRITING.md#headings)).
2. **The two parts**: the overview can be understood by a reader new to the topic without reading part 2 ([Part
   1](WRITING.md#part-1-the-overview)). Content too technical for it is moved to part 2 and replaced by a plain
   explanation; content of part 2 that a newcomer needs is explained in the overview as well. No address appears outside
   the glossary and the commands of `## How to verify` in `REVIEW.md`.
3. **Wording**: one term per thing, one thing per term, no ambiguous words, no links outside the topic folder
   ([Wording](WRITING.md#wording)).
4. **Ideas are introduced before they are used**, in each part on its own: the overview does not rely on part 2, and the
   glossary does not count as an introduction.
5. **Names**: members written as `Class::member` in part 2, never by offset ([Glossary and
   naming](WRITING.md#glossary-and-naming)).
6. **The patch**: its comments and enums follow [Writing the template changes](PATCHES.md#writing-the-template-changes).
   A comment that says where a member is set, read or tested is removed from the patch, and the fact moved into the
   document if it is not there already. The reviewer regenerates the patch from a fresh work copy and checks it again
   with `git apply --check` and `mk7 --templates ... verify`; a patch that no longer applies because `template/` changed
   is updated ([When the base commit has moved on](PATCHES.md#when-the-base-commit-has-moved-on)).

The reviewer may reword, reorder, split and move content between sections, but must not change what a claim says. It may
look at the binary to understand a passage, but if it finds something that looks wrong, or a passage that cannot be made
clear without changing its meaning, it does not fix it; it writes it down in the review. Then the reviewer:

1. Adds a `### Document review` subsection to `## Review` in `REVIEW.md`: what was changed, and what was found that
   looks factually wrong or could not be resolved.
2. If nothing factual was found, sets `Status: verified` and moves the folder to `final/<topic>/`. From then on the
   names in the document and the patch are final; only the human changes them. Otherwise sets the status back to
   `pending verification` and leaves the folder where it is, so that the topic goes through pass 2 again.
3. Stops and reports.

## Human review

The human reviews `final/<topic>/`. What they approve, they apply and commit themselves: patches go into `template/`,
and documents worth keeping as context for future research are moved to `docs/research/<topic>/`, with their
`REVIEW.md` and a line in the [index of reviewed research](../research/INDEX.md). The agent does neither on its own; it
moves a document to `docs/research/` and indexes it only when the human, having reviewed it, asks for it.

## The three folders

| Folder | Holds | Trust |
| --- | --- | --- |
| `pending-verification/<topic>/` | results of pass 1, and of pass 2 until pass 3 is done | unverified; never use as context for other research |
| `final/<topic>/` | results that passed both reviews by the agent | awaiting human review; may be consulted, but is not established fact |
| `docs/research/<topic>/` | documents a human has reviewed and accepted | a good source when relevant, but `eur2` wins when they disagree |

`docs/research/` is the agent's long-term knowledge of the game, and [docs/research/INDEX.md](../research/INDEX.md) is
its index, one line per subject. It holds what future research needs and that is not visible in `template/`: how
subsystems relate, conventions of the compiler and the engine, names and addresses of important functions and tables in
`eur2`, dead ends that are not worth retrying.

# Vocabulary Expansion Plan

## Goal

Build a large starter vocabulary library for stories and training by importing a frequency-ranked core word list into a Hebrew-first canonical lemma model, with English attached as the translation side.

## Source Strategy

Use `wordfreq` as the primary source for common Hebrew words, and use the English wordlist as the translation reference side.

`wordfreq` provides frequency ranking and Zipf-style frequency estimates, not CEFR-style difficulty labels such as A1, A2, B1, or C2.

If we want difficulty levels in the app, we should derive and store our own internal tier from frequency and editorial review rather than treat it as source data from `wordfreq`.

Why this source:

- It supports more than 40 languages, including English and Hebrew.
- It provides ranked word frequencies rather than a fixed hand-curated list.
- It can return the most common `n` words or iterate through a language's wordlist in frequency order.

## Recommended Size

Start with about 3,000 words.

Suggested rollout:

- Phase 1: 500 to 800 words for core story and quiz coverage.
- Phase 2: expand to 1,500 words once the import and review workflow is stable.
- Phase 3: reach 3,000 words as the default starter library.

Why 3,000:

- It is large enough to cover a broad amount of everyday story vocabulary.
- It stays manageable for review, duplicate detection, and translation cleanup.
- It is small enough to keep quality high without turning the first release into a giant curation project.

## Data Shape

Each imported word should map to canonical vocabulary records:

- `lemma`: one stable vocabulary record per concept.
- `sense`: the primary meaning and translation link.
- `lemma_form` table: primary unvocalized surface form plus optional non-primary rows.
- One non-primary `lemma_form` row can store the optional vocalized Hebrew form; English does not need a vocalized row.

Do not store the vocalized Hebrew form in extra data if it is part of the word itself. Keep it as a real surface-form row so search, display, and quest lookup can use it consistently.

## Import Workflow

1. Generate or download a ranked list from `wordfreq`.
2. Filter it to the Hebrew language and part-of-speech mix needed for stories.
3. Derive English translations from a bilingual lexicon first, then use machine translation only as a fallback.
4. Normalize Hebrew by stripping nikkud for the primary searchable form.
5. Preserve the vocalized Hebrew form as a non-primary `lemma_form` when available.
6. Insert or merge Hebrew lemmas into the canonical vocabulary tables.
7. Attach English translations, then flag duplicates and near-duplicates for admin review.
8. Attach story tags and optional quest links.

## English Translation Derivation

Recommended order:

1. Use a bilingual Hebrew-English dictionary or Wiktionary-derived sense map as the primary source.
2. If the Hebrew word has multiple senses, choose the English gloss that best matches the intended story level and context.
3. If no good dictionary match exists, use machine translation to suggest a candidate gloss.
4. Run Ollama over the Hebrew/English pair to flag weak or suspicious matches.
5. Require human review before publishing any pair with low confidence or multiple plausible senses.

Preferred source stack:

- Bilingual dictionary or Wiktionary-derived data first.
- Machine translation second.
- Ollama semantic review third.
- Human approval last.

This works better than trying to build the English side from the Hebrew frequency list alone, because frequency gives ranking, not translation meaning.

## Implementation Notes

- Use a Python script for bulk import and repeatable regeneration.
- Keep the import source file in CSV or JSON so it can be reviewed in git.
- Make the script idempotent so reruns update existing lemmas instead of creating duplicates.
- Prefer manual approval for publish state, even if the import itself is automated.

## Validation and Alignment

- Treat Hebrew as the canonical source list and align English as the translation side by concept instead of by exact surface string.
- Require one canonical Hebrew lemma per concept and at least one English translation per aligned concept unless the English translation is genuinely missing.
- Store the Hebrew vocalized form only as a non-primary `lemma_form` row on the Hebrew lemma, never as a separate lemma.
- Reject duplicate imports when the normalized Hebrew primary form and language already match an existing canonical lemma.
- Reject imports where the primary Hebrew row still contains nikkud or where the vocalized row is incorrectly marked as primary.
- Mark unmatched items for review rather than auto-creating a second lemma with the same meaning.
- Use Ollama as a semantic review step to flag Hebrew/English pairs that look mismatched, too loose, or duplicated.
- Treat Ollama as a reviewer, not as the final authority; human review still decides whether a pair is accepted.
- Do not publish the starter library until duplicate checks pass and the unresolved alignment count is within an agreed threshold.

## Attribution

- Credit `wordfreq` in the project README or a NOTICE file as the source library used to generate the starter list.
- Credit the author as Robyn Speer, matching the upstream notice.
- If we use the vocabulary data in academic work, include the Zenodo citation from the `wordfreq` README.
- If we redistribute a derived starter list, keep the attribution in a text file next to the export instead of relying on CSV metadata.

## Practical Recommendation

If you want a single target to start with, do this:

- Phase 1: 500 to 800 words for core story and quiz coverage.
- Phase 2: expand to 1,500 words once the import and review workflow is stable.
- Phase 3: reach 3,000 words as the default starter library.

Hebrew is the anchor language for the starter set; English is attached as the translation layer.

English does not need a vocalized variant.

For English derivation, start with a dictionary-backed gloss and only fall back to machine translation when the dictionary does not give a clean match.

That gives you enough coverage to write short stories, quests, and quizzes without overbuilding the vocabulary system first.

## Next Step

Build the importer with `scripts/vocab_importer.py`, then generate the starter list from `wordfreq`, then review the results in the admin vocabulary UI.
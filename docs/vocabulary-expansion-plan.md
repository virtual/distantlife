# Vocabulary Expansion Plan

## Goal

Build a large starter vocabulary library for stories and training by importing a frequency-ranked core word list into the canonical lemma model.

## Source Strategy

Use `wordfreq` as the primary source for common words.

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
- `lemma_form`: primary unvocalized surface form.
- `lemma_form` extra row: optional vocalized Hebrew form, stored as a non-primary form.

Do not store the vocalized Hebrew form in extra data if it is part of the word itself. Keep it as a real surface-form row so search, display, and quest lookup can use it consistently.

## Import Workflow

1. Generate or download a ranked list from `wordfreq`.
2. Filter it to the language and part-of-speech mix needed for stories.
3. Normalize Hebrew by stripping nikkud for the primary searchable form.
4. Preserve the vocalized Hebrew form as a non-primary `lemma_form` when available.
5. Insert or merge into the canonical vocabulary tables.
6. Flag duplicates and near-duplicates for admin review.
7. Attach translations, story tags, and optional quest links.

## Implementation Notes

- Use a Python script for bulk import and repeatable regeneration.
- Keep the import source file in CSV or JSON so it can be reviewed in git.
- Make the script idempotent so reruns update existing lemmas instead of creating duplicates.
- Prefer manual approval for publish state, even if the import itself is automated.

## Practical Recommendation

If you want a single target to start with, do this:

- English: 3,000 common words.
- Hebrew: the matching high-frequency set you can cleanly align to the same story themes, even if the initial Hebrew list is smaller than the English one.

That gives you enough coverage to write short stories, quests, and quizzes without overbuilding the vocabulary system first.

## Next Step

Build the importer first, then generate the starter list from `wordfreq`, then review the results in the admin vocabulary UI.
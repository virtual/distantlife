# Quest Vocabulary Cutover Plan

## Goal

Move Train and Quest vocabulary onto a single canonical source of truth without migrating the legacy CSV or JSON content in place.

The new system should read only the new model after cutover. Legacy tables, upload flows, and quest JSON files can remain as historical artifacts until they are explicitly retired.

## Implementation Checklist

### 1. Canonical Vocabulary Model

- Define the new vocabulary tables or schema boundary around a lemma-level canonical record.
- Store a stable identifier for each lemma and keep its primary sense/translation links attached to that identifier.
- Keep language, translation, part-of-speech, form metadata, and optional nikkud/vocalized spelling attached to that record or its surface-form rows.
- Make the model the shared source for both Train and Quest surfaces.

### 2. Quest Vocabulary References

- Replace free-text `vocabulary_targets` entries with stable lemma IDs or other canonical keys.
- Update quest episode content to reference canonical items directly, while allowing display variants such as unvocalized and nikkudized forms.
- Ensure quiz prompts and story references can resolve from the same lemma-based source.

### 3. Train Import Pipeline

- Replace the CSV-only ingestion path with a writer for the canonical model.
- Keep existing CSV files as input assets if useful, but do not require migration of their current storage format.
- Make train set membership a relationship to canonical lemma/sense items, not a separate word copy.
- Preserve optional nikkud or other surface-form variants during import instead of flattening them into a single string.

### 4. Admin Vocabulary Management

- Add an admin vocabulary editor for creating and updating lemma records directly in the UI.
- Support search, filter, and duplicate-detection tools so admins can find existing vocabulary before adding a new item.
- Let admins manage surface forms, translations, optional nikkud, and train-set membership from one place.
- Provide a quest-linking view so admins can attach existing vocabulary items to quest episodes without hand-editing JSON.
- Keep CSV upload as a bulk-import option, but make the UI the primary day-to-day management path.

### 4a. Admin Workflow

- Vocabulary Library: searchable list of canonical lemmas with filters for language, part of speech, status, and train-set usage.
- Detail Panel: one record view that shows lemma, translations, surface forms, optional nikkud, train-set links, and quest links.
- Draft Editor: create or update a vocabulary item in draft state, with inline validation before save.
- Duplicate Check: show possible matches before creation so admins can reuse an existing lemma instead of cloning one.
- Review Queue: surface generated vocabulary drafts from quest stories with a clear accept, edit, reject, or merge action.
- Publish Action: move an approved draft into the published state and write version history for rollback.
- Conflict Handling: if a lemma already exists, prompt the admin to merge surface forms or attach the new quest link rather than creating a second canonical record.
- Bulk Import Path: keep CSV upload as a separate bulk action that lands in draft/review, not immediate publish.

Recommended admin states:

- Draft: created manually or generated from a quest, not yet visible to learners.
- Review: ready for admin validation and merge decisions.
- Approved: validated and waiting for publish.
- Published: available to Train and Quest surfaces.
- Archived: retained for history but hidden from normal authoring flows.

### 5. Generate Vocabulary From Quest Story

- Add a quest-story analysis view that suggests candidate vocabulary from the episode title, story text, speech lines, sentences, and quiz prompts.
- Let the UI generate a draft vocabulary set from the story, then require admin review before it becomes authoritative.
- Surface matches against existing canonical lemmas first so admins can reuse vocabulary already in Train.
- Allow admins to add missing lemmas, nikkud variants, translations, and train-set links during the review step.
- Store the generated set as references to canonical vocabulary items, not as a second copy of the text.

### 6. Quest Rendering and Lookup

- Update quest pages to read vocabulary from the canonical lemma model.
- Remove the text-match fallback that searches `lemma_form.value` for quest targets.
- Resolve translations and display forms through the shared lemma identifier instead of raw strings.

### 7. Validation and Safety

- Validate that each quest reference resolves to an existing vocabulary item.
- Validate that optional nikkud or surface-form variants remain attached to the lemma instead of being lost.
- Fail fast on missing IDs, missing translations, or malformed quest content.
- Add tests for quest loading, train rendering, and translation lookup against the new source.

### 8. Workflow Best Practices

- Use explicit content states such as draft, review, approved, and published for both vocabulary sets and quest-linked vocabulary.
- Record provenance for generated vocabulary so admins can see whether a term came from a quest story, manual entry, CSV import, or an existing train set.
- Show a diff or preview before publish so admins can compare the generated draft against existing canonical vocabulary.
- Detect duplicates and near-duplicates before saving, especially when the same lemma appears with and without nikkud.
- Keep bulk generation and bulk import reversible so a bad generation pass can be discarded without touching stable vocabulary.
- Preserve author notes or review comments when a generated draft is promoted to canonical status.

### 9. Publish and Rollback

- Publish vocabulary sets only after validation passes and an admin approves the draft.
- Store enough version history to roll back a bad publish without recreating the data by hand.
- Make rollback a controlled admin action with clear visibility into what changes will be reverted.
- Prefer soft-delete or archival for recently published items until the workflow proves stable.

## Legacy Data Cleanup Plan

### 1. Inventory Legacy Surfaces

- List all old tables, helpers, and routes that only support the legacy model.
- Identify quest JSON fields that are no longer consumed after cutover.
- Identify admin upload and edit paths that write to legacy structures.

### 2. Stop Writing Legacy Data

- Disable new writes to the old tables once the canonical path is live.
- Keep the old files and tables read-only during the transition window.

### 3. Remove Stale Read Paths

- Delete helper functions and queries that only support the old schema.
- Remove fallback logic that tries to infer vocabulary from legacy text fields.
- Keep the removal phase separate from the cutover phase so failures are easier to isolate.

### 4. Archive or Delete Obsolete Content

- Archive legacy JSON and CSV assets if you want them for reference.
- Delete old content only after the new model is verified in production-like use.
- Record what was removed so the cleanup is auditable.

## Recommended Order

1. Build the canonical vocabulary model.
2. Switch Train writes to the new model.
3. Switch Quest reads to the new model.
4. Validate the new end-to-end flow.
5. Freeze legacy writes.
6. Remove stale reads.
7. Archive or delete obsolete legacy data.

## Permissions

**Non-Admin Users:**
- Read-only access to the vocabulary library (view, search, filter).
- Cannot create, edit, approve, publish, or delete vocabulary.
- Can view train sets, quest content, and vocabulary translations for learning purposes.

**Admin Users:**
- Full control over vocabulary creation, editing, approval, and publishing.
- Can generate vocabulary from quest stories and review generated drafts.
- Can upload CSV files for bulk vocabulary import.
- Can manage train-set membership and quest-episode links.
- Can rollback published vocabulary and view version history.
- Can archive or delete vocabulary items.
- All admin actions are logged for audit purposes.

## Cutover Rule

The app should never need to migrate old CSV or JSON content into the new system in place. Instead, the new model should be introduced alongside the legacy content, then made authoritative when the cutover is complete.

## Cutover Checklist

- Backup: take a full DB snapshot and export of legacy CSV/JSON assets before any cutover change.
- Feature flag: implement an admin-only feature flag (`vocab_canonical_enabled`) to toggle canonical reads/writes.
- Compatibility shim: implement a short-lived shim so legacy reads map to canonical IDs (read-only) for verification.
- Smoke tests: end-to-end tests for train import, quest rendering, and quiz flows using canonical vocab.
- Admin UI readiness: ensure Draft Editor, Review Queue, Duplicate Check, and Quest Linker are deployed and accessible.
- Incremental rollout: enable the feature flag in staging, run validation, then enable for a limited admin group in production.
- Validation run: cross-check counts (train set membership, quest references) between legacy and canonical systems.
- Monitoring: add metrics and alerts for missing lookup failures, high duplicate rates, and publish errors.
- Freeze window: schedule a short write-freeze to stop legacy writes before disabling legacy write paths.
- Final switch: flip the feature flag to canonical-only reads/writes; keep a fast rollback path.

## Deployment & Rollback Checklist

Pre-deploy (staging):
- Run DB backup and export legacy CSV/JSON.
- Deploy new schema and API endpoints behind feature flag.
- Run automated smoke tests.
- Run manual admin acceptance tests: create, edit, publish, merge, generate-from-quest.

Canary (limited production):
- Enable `vocab_canonical_enabled` for admin group only.
- Monitor errors, missing lookups, and user-reported issues for 24–48 hours.
- Validate that experience/quiz scoring matches previous behavior for test accounts.

Cutover (production):
- Communicate the maintenance window to stakeholders.
- Put system into read-only mode for legacy writes (if possible).
- Flip feature flag to full production.
- Run quick verification script to ensure no unresolved quest references remain.
- Monitor logs and metrics for immediate regressions.

Rollback:
- If critical errors occur, flip the feature flag off to restore legacy behavior.
- Use DB snapshot to restore data only if irreversible destructive changes were made (avoid unless necessary).
- Re-open the issue ticket and investigate. Keep the admin group on the staging flag while fixes are deployed.

Post-cutover:
- After 72 hours of stable operation, proceed with legacy read-path removal on a maintenance window.
- Archive legacy CSV/JSON assets and keep them in long-term storage for audit.
- Update documentation and notify teams of the change.

## URL and Path Naming Convention

- All newly created URLs, route paths, endpoint paths, and filesystem paths must use dash-case (`-`) instead of underscores (`_`).
- Apply this to new admin routes, quest/vocabulary linkage paths, API endpoints, migration filenames, and any new content path keys.
- Existing legacy paths may remain unchanged during transition, but any new path introduced during cutover must follow dash-case.
- Add a review check in PRs to reject new underscore-based paths unless there is a strict backward-compatibility requirement.
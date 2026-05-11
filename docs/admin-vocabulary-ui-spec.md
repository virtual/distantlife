# Admin Vocabulary UI Spec

This document outlines the admin interface for managing canonical vocabulary, including screens, fields, actions, and navigation flows.

## Navigation and Top-Level Routes

- `/admin/vocabulary` - Vocabulary Library (default landing)
- `/admin/vocabulary/new` - Draft Editor (create new)
- `/admin/vocabulary/<vocab_id>` - Detail Panel (view one record)
- `/admin/vocabulary/<vocab_id>/edit` - Draft Editor (edit existing)
- `/admin/vocabulary/review` - Review Queue (generated drafts)
- `/admin/vocabulary/import` - Bulk Import (CSV upload)
- `/admin/quests/<quest_id>/vocabulary` - Quest Vocabulary Linker (attach vocabulary to quest episodes)

---

## Screen 1: Vocabulary Library

**Purpose:** Search, filter, and browse canonical vocabulary items.

**URL:** `/admin/vocabulary`

**Layout:**

```
-------------------------------------------------------------
| Vocabulary Library                               [+ New] [?] |
-------------------------------------------------------------
| Search [__________________]                                   |
| Filter: Language [▼ Hebrew] POS [▼ All] Status [▼ Published] |
| Sort: [▼ Name A-Z]                                            |
-------------------------------------------------------------
| ID | Lemma     | Translation        | POS   | Status    | Uses |
----+-----------+--------------------+-------+-----------+------+
| 42 | רעב       | hunger/famished    | Adj   | Published |  1   |
| 43 | סל        | basket             | Noun  | Published |  2   |
| 44 | גן        | garden             | Noun  | Published |  3   |
| 45 | זרע       | seed               | Noun  | Draft     |  0   |
----+-----------+--------------------+-------+-----------+------+
| Show [▼ 20] rows | 1-4 of 127              [< Prev] [Next >] |
-------------------------------------------------------------
```

**Fields:**

- Search box: filters by lemma, translation, or nikkud form (case-insensitive, substring match).
- Language dropdown: Hebrew, English, or both.
- POS dropdown: All, Noun, Verb, Adjective, etc.
- Status dropdown: Published, Approved, Review, Draft, Archived.
- Sort dropdown: Name A-Z, Name Z-A, Recently Updated, Status.
- Rows per page dropdown: 20, 50, or 100 rows (default 20).

**Actions:**

- Click lemma cell: open Detail Panel.
- [+ New]: navigate to Draft Editor (create).
- [Import CSV]: navigate to Bulk Import.
- [Review Queue]: navigate to Review Queue.
- [?]: show help tooltip with search examples.

**List Columns:**

- ID: unique vocabulary identifier.
- Lemma: primary surface form with nikkud if available.
- Translation: primary translation in preferred language.
- POS: part of speech (Noun, Verb, Adj, etc.).
- Status: badge with color (Published=green, Draft=gray, Review=yellow, Archived=strikethrough).
- Uses: count of quest episodes using this vocabulary.

---

## Screen 2: Detail Panel

**Purpose:** View all metadata for a single vocabulary item, with options to edit or link to quests/sets.

**URL:** `/admin/vocabulary/<vocab_id>`

**Layout:**

```
-------------------------------------------------------------
| Back to Library | Vocabulary: רעב (hungry)       [Edit] [•••] |
-------------------------------------------------------------
| Status: Published  | Last Updated: May 5, 2026 at 2:14 PM    |
| Created by: admin1 | Version: 3 (see history)                |
-------------------------------------------------------------
| LEMMA METADATA                                                |
| Lemma ID: 42                                                  |
| Language: Hebrew                                              |
| Part of Speech: Adjective                                     |
| Pronunciation: ra-AV                                          |
| Audio File: [hunger.mp3]                                      |
| Image: [hungry.jpg] [⊘ Clear]                                |
|                                                               |
| SURFACE FORMS                                                 |
| Primary (Unvocalized): רעב                                   |
| Optional (With Nikkud): רָעֵב                                |
| Search Key: RAV                                               |
|                                                               |
| PRIMARY TRANSLATION (English)                                 |
| Translation: hungry / famished                                |
| Definition: feeling or showing hunger                         |
|                                                               |
| TRAIN SET MEMBERSHIP                                          |
| Sets: [Food & Garden Vocab] [Hebrew Adjectives]              |
| (click to add more sets)                                      |
|                                                               |
| QUEST LINKS                                                   |
| Quests:                                                       |
| - hungry_faun_01 > Episode 1: "The Empty Basket"            |
| - hungry_faun_01 > Episode 2: "The First Harvest"           |
| (click to add/remove quest links)                            |
|                                                               |
| REVIEW NOTES (if in review)                                   |
| [None]                                                        |
|                                                               |
| VERSION HISTORY                                               |
| v3: Published by admin1 (May 5, 2026)                         |
| v2: Moved to Approved (May 4, 2026)                          |
| v1: Created as Draft (May 3, 2026)                           |
| [See full diff]                                              |
-------------------------------------------------------------
```

**Key Sections:**

- **Header:** Lemma name, status badge, edit/menu buttons.
- **Metadata:** Lemma ID, language, POS, pronunciation, audio file link.
- **Surface Forms:** unvocalized and optional nikkud variants, search key.
- **Primary Translation:** main translation text and definition.
- **Train Set Membership:** list of sets this vocabulary belongs to, with add/remove actions.
- **Quest Links:** quests and episodes using this vocabulary, with add/remove actions.
- **Review Notes:** if in review state, show admin comments (editable by reviewer).
- **Version History:** timeline of state changes with diffs.

**Actions:**

- [Edit]: navigate to Draft Editor for this item.
- [•••] menu: Edit, Duplicate, Archive, Delete (admin-only).
- Add/remove train sets: dialog to select from available sets.
- Add/remove quest links: dialog to select from quests and episodes.
- [See full diff]: show detailed version diff in modal.

---

## Screen 3: Draft Editor

**Purpose:** Create or edit a vocabulary item in draft state.

**URL:** `/admin/vocabulary/new` or `/admin/vocabulary/<vocab_id>/edit`

**Layout:**

```
-------------------------------------------------------------
| Back to Library | New Vocabulary Item              [Save Draft] |
-------------------------------------------------------------
| Status: Draft                                                 |
|                                                               |
| LEMMA METADATA                                                |
| Language: [▼ Hebrew]                                          |
| Part of Speech: [▼ Noun]                                      |
| Pronunciation: [_________________]                            |
| Audio File: [Choose file]  [⊘ Clear]                          |
| Image: [Choose file]  [⊘ Clear]                               |
|                                                               |
| SURFACE FORMS                                                 |
| Primary (Unvocalized): [רעב_________________]                |
| Optional (With Nikkud): [רָעֵב________________]               |
| (Search key will auto-generate from primary form)             |
|                                                               |
| PRIMARY TRANSLATION (English)                                 |
| Translation: [hungry / famished__________]                    |
| Definition: [feeling or showing hunger____]                   |
|                                                               |
| TRAIN SET MEMBERSHIP                                          |
| Add to sets: [Search or select...]  [+ Add Set]              |
| Selected: [Food & Garden] [Hebrew Adjectives] [×] [×]        |
|                                                               |
| NOTES (optional)                                              |
| [Internal notes or review comments...]                        |
|                                                               |
| SAVE OPTIONS                                                  |
| [ ] Publish immediately (requires admin approval)             |
|                                                               |
| [Save Draft] [Cancel]                                         |
-------------------------------------------------------------
```

**Key Fields:**

- Language: dropdown (Hebrew, English, etc.).
- POS: dropdown (Noun, Verb, Adjective, Adverb, etc.).
- Pronunciation: text field.
- Audio File: file chooser (optional).
- Image: file chooser (optional; for future visual learning features).
- Primary Form (Unvocalized): text field, required.
- Optional Form (Nikkud): text field, optional.
- Translation: text field, required.
- Definition: textarea, optional.
- Train Sets: multi-select with search.
- Notes: textarea for internal comments or review feedback.

**Validation:**

- Primary form is required and must not be empty.
- Translation is required.
- Language and POS must be set.
- Show inline validation errors (red highlight, tooltip) on blur or submit attempt.

**Actions:**

- [Save Draft]: validate and save to draft state; show confirmation.
- [Cancel]: discard changes and return to Library.
- [Check for Duplicates]: search for existing lemmas with similar primary or nikkud form before save (optional flow).
- Publish checkbox: if checked, mark as approved and wait for publish action (admin review may still be needed).

---

## Screen 4: Review Queue

**Purpose:** Show generated vocabulary drafts from quest stories, waiting for admin review and merge decisions.

**URL:** `/admin/vocabulary/review`

**Layout:**

```
-------------------------------------------------------------
| Back to Library | Review Queue                    [Generate] |
-------------------------------------------------------------
| Filter: [▼ Generated from Quest] [▼ All Languages]            |
| Sort: [▼ Newest First]                                         |
-------------------------------------------------------------
| DRAFT 1 (Generated from hungry_faun_01 Episode 1)             |
| Lemma: גן (garden)                                            |
| Translation: garden                                           |
| POS: Noun                                                     |
| Image: [garden.jpg]                                           |
| Provenance: Generated from story text                         |
| Suggested Train Sets: [Food & Garden Vocab] [▼ None]         |
| Suggested Quest Links: [hungry_faun_01 Ep1] [hungry_faun_01 Ep2] |
| Status: [Match Found] Merge with existing #44 (garden)       |
|   [Merge] [Reject] [Edit as New]                              |
|                                                               |
| DRAFT 2 (Generated from hungry_faun_01 Episode 1)             |
| Lemma: עדין (tender)                                          |
| Translation: tender / delicate                                |
| POS: Adjective                                                |
| Provenance: Generated from quiz prompt                        |
| Suggested Train Sets: [▼ None]                                |
| Suggested Quest Links: [hungry_faun_01 Ep1]                   |
| Status: [No Match] Ready to approve                           |
|   [Approve] [Edit] [Reject]                                   |
|                                                               |
| DRAFT 3 (Generated from counting_cerberus_01 Episode 1)       |
| Lemma: ספור (count)                                          |
| Translation: to count                                         |
| POS: Verb                                                     |
| Provenance: Generated from story text                         |
| Suggested Train Sets: [▼ None]                                |
| Suggested Quest Links: [counting_cerberus_01 Ep1-3]           |
| Status: [Duplicate Check] Similar to #127 (ספירה)            |
|   [View Similar] [Merge] [Edit] [Keep Both]                   |
|                                                               |
| Showing: 3 of 12 pending reviews                              |
-------------------------------------------------------------
```

**Fields per Draft:**

- Lemma: unvocalized and nikkud form.
- Translation: suggested translation.
- POS: inferred part of speech.
- Provenance: where it came from (quest story text, quiz prompt, etc.).
- Suggested Train Sets: auto-detected set recommendations (clickable to override).
- Suggested Quest Links: episodes where vocabulary was detected.
- Status: Match Found / No Match / Duplicate Check (with action buttons).

**Actions:**

- [Merge]: combine with an existing vocabulary item and link the quest.
- [Approve]: accept the draft as-is and promote to published.
- [Edit]: open in Draft Editor for tweaks before approve.
- [Reject]: discard the draft without saving.
- [View Similar]: open a modal showing similar existing vocabulary.
- [Generate]: trigger a new vocabulary extraction from a quest (if not bulk mode).

---

## Screen 5: Duplicate Check (Modal)

**Purpose:** Prevent duplicate canonical vocabulary when creating a new item.

**URL:** (modal overlay on Draft Editor or Review Queue)

**Layout:**

```
-------------------------------------------------
| Possible Duplicates Found                      |
-------------------------------------------------
| You are creating: רעב (hungry)                         |
|                                                         |
| We found similar items in the vocabulary:              |
|                                                         |
| 1. רעב (hungry) - ID #42                              |
|    Status: Published                                   |
|    Translation: hungry / famished                      |
|    Nikkud: רָעֵב                                       |
|    Image: [hungry.jpg]                                 |
|    Train Sets: [Food & Garden Vocab]                   |
|    Quests: hungry_faun_01 (2 episodes)                |
|    [Select]                                            |
|                                                         |
| 2. רעבון (starvation) - ID #98                         |
|    Status: Published                                   |
|    Translation: starvation                             |
|    Nikkud: [None]                                      |
|    Train Sets: [None]                                  |
|    Quests: [None]                                      |
|    [Select]                                            |
|                                                         |
| If none of these match, you can:                       |
| [Create New Vocabulary]                                |
| [Cancel]                                               |
-------------------------------------------------
```

**Logic:**

- Search for lemmas with similar unvocalized or nikkud forms.
- Show matches sorted by string similarity or date (newest first).
- For each match, show status, translation, sets, and quest links.

**Actions:**

- [Select]: choose an existing lemma to merge with (adds new quest links or train sets).
- [Create New Vocabulary]: bypass duplicates and create a new canonical record (admin confirms intent).
- [Cancel]: return to Draft Editor without saving.

---

## Screen 6: Quest Vocabulary Linker

**Purpose:** Attach vocabulary to quest episodes without hand-editing JSON.

**URL:** `/admin/quests/<quest_id>/vocabulary`

**Layout:**

```
-------------------------------------------------------------
| Back to Quest List | Quest: hungry_faun_01              |
-------------------------------------------------------------
| Episode 1: "The Empty Basket"                           |
| Current Vocabulary Targets: 8 items                     |
| [Edit Targets] [Generate from Story] [Preview]          |
| [hungry] [basket] [garden] [seed] [soil] [plant]       |
| [water] [carrot]                                        |
|                                                         |
| Add vocabulary to this episode:                         |
| Search: [________________________________]              |
| Suggested: (showing matches to "hungry", "basket", etc) |
| [hungry] (ID #42) [+ Add]                              |
| [basket] (ID #43) [+ Add]                              |
| [hunger] (ID #101) [+ Add]                             |
|                                                         |
| Episode 2: "The First Harvest"                          |
| Current Vocabulary Targets: 8 items                     |
| [Edit Targets] [Generate from Story] [Preview]          |
| [leaf] [orange] [pull] [wash] [cook] [soup]            |
| [share] [friend]                                        |
|                                                         |
| Add vocabulary to this episode:                         |
| Search: [________________________________]              |
|                                                         |
| [Save All Changes] [Cancel]                             |
-------------------------------------------------------------
```

**Key Features:**

- List all episodes in the quest.
- Show current vocabulary targets for each episode (draggable to reorder, or clickable to remove).
- Search and suggest vocabulary from the canonical library.
- [Generate from Story]: auto-extract candidate vocabulary from episode text and prompt review.
- [Preview]: show how vocabulary will render on the quest page.
- [Edit Targets]: open a modal to manually edit the target list (power-user feature).

**Actions:**

- [+ Add]: add a vocabulary item to the episode.
- [Remove] (on each vocab badge): remove an item from the episode.
- [Generate from Story]: trigger extraction and review flow.
- [Preview]: show a mockup of how quest page will look with current vocabulary.
- [Save All Changes]: commit changes and return to quest detail page.

---

## Screen 7: Bulk Import (CSV Upload)

**Purpose:** Upload CSV vocabulary data and land it in review state.

**URL:** `/admin/vocabulary/import`

**Layout:**

```
-------------------------------------------------------------
| Back to Library | Bulk Import CSV                       |
-------------------------------------------------------------
| Upload vocabulary data:                                 |
| CSV format (required columns):                          |
| Language, Primary Form, Nikkud Form (optional),         |
| Translation, POS, Pronunciation, Train Set (optional)   |
|                                                         |
| [Choose File] example-vocabulary.csv                    |
|                                                         |
| Import options:                                         |
| [ ] Detect and merge duplicates                         |
| [ ] Auto-approve if no conflicts                        |
| [✓] Land in review state (default)                      |
|                                                         |
| [Upload & Review] [Cancel]                              |
-------------------------------------------------------------
|                                                         |
| RESULTS (after upload)                                  |
|                                                         |
| Import Summary:                                         |
| - Rows processed: 42                                    |
| - New vocabulary created (draft): 28                    |
| - Merged with existing: 12                              |
| - Duplicates flagged: 2                                 |
| - Errors: 0                                             |
|                                                         |
| Next steps:                                             |
| [Go to Review Queue] [Go to Library]                    |
-------------------------------------------------------------
```

**CSV Format:**

```
Language,Primary Form,Nikkud Form,Translation,POS,Pronunciation,Image File,Train Set
Hebrew,רעב,רָעֵב,hungry,Adjective,ra-av,hungry.jpg,Food & Garden Vocab
Hebrew,סל,סַל,basket,Noun,sal,basket.jpg,Food & Garden Vocab
Hebrew,גן,גַן,garden,Noun,gan,garden.jpg,Food & Garden Vocab
```

**Validation:**

- Check required columns (Language, Primary Form, Translation, POS).
- Flag duplicates or near-matches.
- Land all rows in draft state for review.
- Show summary of what was imported.

**Actions:**

- [Upload & Review]: process the file and show summary.
- [Go to Review Queue]: jump to review queue to process generated drafts.
- [Go to Library]: return to vocabulary library.

---

## State Transitions and Permissions

### Vocabulary Item States

```
Draft → Approved → Published
  ↓        ↓          ↓
  └─────→ Reject ──→ Archived
                      ↓
                    Restore
```

**Permissions:**

- **Non-Admin:** read-only access to vocabulary library; cannot create, edit, or publish.
- **Admin:** full control over vocabulary creation, editing, approval, publishing, deletion, rollback, and bulk import.

### Permission Matrix

| Action                    | Non-Admin | Admin |
|---------------------------|-----------|-------|
| View Vocabulary Library   | ✓         | ✓     |
| Create/Edit Draft         |           | ✓     |
| Move to Approved          |           | ✓     |
| Publish                   |           | ✓     |
| Delete/Archive            |           | ✓     |
| Rollback Version          |           | ✓     |
| Bulk Import               |           | ✓     |
| Generate from Quest       |           | ✓     |
| Review Generated Drafts   |           | ✓     |

---

## Page Flow Diagram

```
Vocabulary Library
  ↓ (click lemma)
Detail Panel
  ↓ [Edit]
Draft Editor
  ↓ [Save Draft]
Detail Panel (updated)
  
Alternative flows:

Library [+ New] → Draft Editor (create) → Library
Library [Review Queue] → Review Queue → [Approve] → Detail Panel
Library [Import CSV] → Bulk Import → Review Queue → Detail Panel
Quest Page [Generate Vocabulary] → Review Queue → Library
Quest Detail [Edit Vocabulary] → Quest Vocabulary Linker → Quest Detail
```

---

## Key Design Principles

1. **Clear State:** Every item shows its status (Draft/Review/Approved/Published/Archived) and who made the last change.
2. **Duplicate Prevention:** Warn admins before creating similar vocabulary; suggest merges.
3. **Reversibility:** All actions (publish, merge, delete) should be undoable or audited.
4. **Provenance:** Track where vocabulary came from (manual, generated, imported) so admins can make informed decisions.
5. **Batch Operations:** Support both single-item and bulk flows without forcing one path over the other.
6. **Learner Isolation:** Only published vocabulary is visible to learners; draft/review items are admin-only.

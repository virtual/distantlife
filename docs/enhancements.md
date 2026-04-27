# Pet Quests: Stories, Quizzes, and Quest Surfaces

Pet Quests turn language learning into a story-driven campaign. The quest page, the sidebar HUD, and the top-of-page alert all reflect the same quest state so the experience stays cohesive instead of repeating the same narrative in multiple places.

## Canonical Quest Loop

Use one quest flow everywhere in the product:

1. **Briefing** - The quest page introduces the problem, goal, or mission.
2. **Train** - The user learns the relevant vocabulary set on the Train page.
3. **Adventure Story** - The story page unlocks once the required words are learned.
4. **Boss Quiz** - The user answers a comprehensive quiz based on the story.
5. **Reward** - The pet receives coins, items, or a permanent visual upgrade.

This flow should be the single authoritative model. Other surfaces should mirror it, not redefine it.

## Quest Access Rules

Each quest type and quest line can restrict access to specific pet types. For the Hungry Carrot example, the quest line should be restricted to the **Faun**.

Suggested access fields in quest metadata:

- `quest_type`
- `quest_line_id`
- `allowed_pet_type_ids`

If a quest line is restricted, child quests should inherit the restriction unless they explicitly override it. If a pet type is not allowed, the quest should be hidden or locked rather than partially exposed.

## Pet Unlock System

New users should start with access to only 5 pet types: **Faun**, **Genie**, **Dragon**, **Cerberus**, and **Cyclops**. Other pets become available through quests, purchases, achievements, or other unlock mechanisms to be determined later.

### Architecture

**Schema approach:**

1. Add a `default_unlocked` boolean flag to the `pet_types` table. Set this to true for the 5 starter pets only.
2. Create a `user_pet_unlocks` table to track which pets each user has unlocked:
   - `user_id` (foreign key to users)
   - `pet_type_id` (foreign key to pet_types)
   - `unlocked_at` (timestamp)
3. When a new user is created, populate `user_pet_unlocks` with the 5 default pets.

### Pet Gender Defaults

Pets should have a default male or female gender assignment that can be used for display and optional language personalization.

**Schema extension:**

1. Add `default_gender` to `pet_types` so each species can define a preferred default:
  - Suggested values: `male`, `female`, `random`
2. Add `gender` to `pets` so each adopted pet stores its actual gender:
  - Suggested values: `male`, `female`
3. On adoption, set `pets.gender` using `pet_types.default_gender`:
  - If default is `male` or `female`, use it directly.
  - If default is `random`, assign male/female randomly.

**Notes:**

- Keep gender on the adopted pet record, not only on `pet_types`, so each pet instance has stable identity.
- Admin tools can optionally support manual correction if needed.

**Routes and templates:**

- The `/adopt` GET route should filter the pet list to show only unlocked pets for that user.
- The adoption validation on POST should check that the requested `pet_type_id` is in the user's unlocked set.

**Unlocking mechanisms:**

- Create a helper function to unlock a pet for a user: `unlock_pet_for_user(user_id, pet_type_id)`.
- Call this function when:
  - A quest completion grants a specific pet unlock.
  - A user makes an in-app purchase.
  - A user earns an achievement.
- All unlock events are logged (see [docs/logs.md](docs/logs.md)).

### Initial Unlock Assignment

On user creation, assign the 5 starter pets:

```python
def initialize_user_pet_unlocks(user_id):
    starter_pets = [1, 6, 10, 26, 16]  # Dragon, Genie, Faun, Cerberus, Cyclops
    for pet_type_id in starter_pets:
        db.execute("INSERT INTO user_pet_unlocks (user_id, pet_type_id, unlocked_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                   (user_id, pet_type_id))
    con.commit()
```

Call this during the signup process after creating the user record.

### Admin Override

Admins (as defined by server authorization policy) should bypass pet unlock restrictions. This allows authorized staff to test, demonstrate, and manage all pets without exposing role constants in public-facing documentation.

**Implementation:**

- In the `/adopt` GET route, check if the user is an admin using `is_admin()`.
- If admin, show all pet types from the database without filtering by `user_pet_unlocks`.
- If not admin, apply the normal unlock filter.
- Optional: Show an "Admin - All Pets" label or similar indicator to distinguish admin view from regular user view.

**Example filter logic:**

```python
if is_admin():
    # Admin sees all pets
    pet_types = db.execute("SELECT * FROM pet_types").fetchall()
else:
    # Regular user sees only unlocked pets
    pet_types = db.execute(
        "SELECT pt.* FROM pet_types pt "
        "INNER JOIN user_pet_unlocks upu ON pt.id = upu.pet_type_id "
        "WHERE upu.user_id = ?", 
        (session_get_int('user_id'),)
    ).fetchall()
```

**POST validation:**

- For admins, allow adoption of any pet type.
- For regular users, validate that the requested `pet_type_id` exists in their unlocked set.

## Quest Announcement Banner

The new quest alert should be a single high-impact banner that appears once, then collapses into the sidebar HUD after the user acknowledges it or navigates away.

### Behavior

- The top banner is the initial attention surface.
- The sidebar is the persistent mission surface.
- The same backend quest state should drive both surfaces.
- The banner should not duplicate quest logic; it should only present the current mission state.

### Content

- Quest icon or avatar thumbnail
- Short quest hook such as "New quest!"
- Brief narrative context
- Primary CTA to view the quest details

### Transition

After the initial trigger, the banner should minimize into the sidebar HUD rather than remaining as a second competing notification.

## Sidebar as Quest HUD

The sidebar should act as a persistent HUD, not as an independent source of quest logic. It mirrors the active quest state and helps the user understand what to do next.

### What the sidebar can show

- **Pet growth**: experience and level
- **Pet name with icon**: pet name shown with a gender icon for quick identity context
- **Speech bubble**: a short mission-focused line that explains the next objective
- **Mini quest tracker**: the current mission title and a checklist of steps
- **Progress indicator**: a bar or ring showing how far the current quest has advanced
- **Call-to-action buttons**: shortcuts such as "Start Adventure" or "Feed"

### Sidebar rules

- The sidebar must reuse quest state from the server.
- It should never calculate its own progress independently.
- It can prompt the user, but it should not branch quest logic on its own.
- Speech bubble lines should come from quest JSON content for the active episode or quest state.
- If vitals are shown, they should be updated by quest completion or routine pet actions.

### Suggested sidebar layout

| Component | Purpose |
| --- | --- |
| Pet avatar | Emotional anchor and visual identity |
| Pet name + gender icon | Fast identity signal and clearer character framing |
| Speech bubble | Mission guidance and narrative tone |
| Status bars | Quick read on pet health or readiness |
| Quest HUD | Current objective and checklist |
| Level or EXP badge | Secondary long-term progression metric |

## Story and Quiz Formats

The story content can support multiple quiz styles without changing the core quest loop.

| Quiz Type | Description |
| --- | --- |
| Cloze tests | Fill in missing words from the story |
| Sentence wizard | Build full sentences from a scrambled word bank |
| Timed speed runs | Test recall speed for a bonus or multiplier |
| Story re-telling | Sequence story sentences in the correct order |

These formats can be combined across episodes so the campaign feels varied while staying aligned to the same vocabulary set.

## Content and Translation Model

Static UI text and dynamic quest content should use different translation paths.

### Static UI text

Use Flask-Babel for chrome text, labels, headings, flashes, and sidebar copy that behaves like UI rather than content.

### Dynamic quest content

Store quest packs, episode titles, story text, quiz prompts, answer options, reward names, and speech-bubble lines in locale-specific JSON files in the repo.

### Content workflow

- AI can generate first drafts of quest content.
- A human must review and approve each locale before publish.
- English and Hebrew should remain in sync through stable IDs and matching structure.
- Content should be localized as content, not hardcoded into templates.

### Translation guidance

- Keep UI keys in the existing message catalog workflow.
- Keep story and quest text outside the translation catalog if it is being managed as locale JSON.
- Use the same ID set across locales so validation can catch missing or mismatched content.

### Dynamic personalization tokens

Quest JSON can include lightweight runtime tokens so content stays localized but still personalized.

- Use token placeholders such as `{{pet_name}}` in story text, quiz prompts, and speech bubble lines.
- At render time, replace tokens from trusted server context (for example: active pet name).
- If no active pet is available, fall back to a safe generic label such as "your pet".
- Keep token names stable across locales so English and Hebrew files have matching structure.
- Escape interpolated values before output so user-provided pet names cannot inject markup.

### Gender-aware content variants

When story grammar depends on pet gender, store full sentence variants in quest JSON rather than assembling grammar fragments at runtime.

- Use structured variants for story text and speech bubble lines:
  - `male`
  - `female`
  - `neutral` (fallback)
- Only add `male`/`female` variants when grammar requires it; otherwise keep one neutral string to reduce content duplication.
- Resolve text using this fallback order: requested gender -> neutral -> male -> female.
- Apply token replacement (for example `{{pet_name}}`) after the gendered variant is selected.
- Keep the same variant keys across locales so parity checks remain reliable.
- Apply the same variant shape to other pet-referential fields when needed, including sentence text and quiz prompts.

This keeps templates simple and avoids fragile grammar logic for Hebrew.

For icon display, keep Font Awesome icon rendering in templates/UI, not inside JSON content text.

**Recommended icon mapping (Font Awesome):**

- `male` -> `fa-solid fa-mars`
- `female` -> `fa-solid fa-venus`
- unknown/legacy-null fallback -> `fa-solid fa-genderless`

**Template example (name + icon):**

```html
<span class="pet-identity">
  <span class="{{ active_pet.gender_icon_class }}" aria-label="{{ active_pet.gender }}"></span>
  <span>{{ active_pet.name }}</span>
</span>
```

This is not significantly more complicated if token usage stays small and explicit. It is usually a low-cost improvement with high player impact.

## Quest Pack Structure

Quest content should be stored in a simple, reviewable structure. Keep the schema compact and make IDs stable across locales.

```json
{
  "quest_id": "hungry_carrot_01",
  "locale": "en",
  "theme": "vegetables",
  "quest_type": "story_quest",
  "quest_line_id": "hungry_carrot",
  "allowed_pet_type_ids": [10],
  "unlock_cost": 50,
  "review_status": "approved",
  "episodes": [
    {
      "episode_id": "hungry_carrot_01_ep1",
      "title": "The Empty Garden",
      "story_text": {
        "male": "{{pet_name}} looked at the garden. There was no carrot. He found a seed and planted it...",
        "female": "{{pet_name}} looked at the garden. There was no carrot. She found a seed and planted it...",
        "neutral": "{{pet_name}} looked at the garden. There was no carrot. {{pet_name}} found a seed and planted it..."
      },
      "speech_bubble_lines": [
        {
          "male": "I should check the garden.",
          "female": "I should check the garden.",
          "neutral": "I should check the garden."
        },
        {
          "male": "I hope we can find a carrot, {{pet_name}}!",
          "female": "I hope we can find a carrot, {{pet_name}}!",
          "neutral": "I hope we can find a carrot, {{pet_name}}!"
        }
      ],
      "sentences": [
        {
          "order": 1,
          "text": {
            "neutral": "{{pet_name}} looked at the garden."
          }
        },
        {
          "order": 2,
          "text": {
            "neutral": "There was no carrot."
          }
        },
        {
          "order": 3,
          "text": {
            "male": "He found a seed and planted it.",
            "female": "She found a seed and planted it.",
            "neutral": "{{pet_name}} found a seed and planted it."
          }
        }
      ],
      "quiz": {
        "questions": [
          {
            "type": "cloze",
            "prompt": {
              "male": "He planted a ____.",
              "female": "She planted a ____.",
              "neutral": "{{pet_name}} planted a ____."
            },
            "answer": "seed"
          },
          {
            "type": "mcq",
            "prompt": "What color was the carrot?",
            "options": ["orange", "blue", "green"],
            "answer": "orange"
          },
          {
            "type": "reorder",
            "prompt": "Put the story sentences in order.",
            "sentence_order": [1, 2, 3]
          }
        ]
      }
    }
  ]
}
```

Suggested metadata fields include locale, version, review status, stable episode IDs, numeric sentence order, quest type, quest line ID, allowed pet type IDs, stable personalization token names, and a consistent gender-variant shape so the English and Hebrew files can be checked for parity and the quest can enforce pet access cleanly.

## Pet Types and IDs

The list below reflects the current `pet_types` seed data. Use these IDs when restricting a quest to specific pet types.

| ID | Pet Type |
| --- | --- |
| 1 | Dragon |
| 2 | UFO |
| 3 | Robot |
| 4 | Unicorn |
| 5 | Gnome |
| 6 | Genie |
| 7 | Bigfoot |
| 8 | Goblin |
| 9 | Oni |
| 10 | Faun |
| 11 | Medusa |
| 12 | Krampus |
| 13 | Godzilla |
| 14 | Werewolf |
| 15 | Haunted |
| 16 | Cyclops |
| 17 | Frog |
| 18 | Ogre |
| 19 | Minotaur |
| 20 | Jackalope |
| 21 | Loch-ness Monster |
| 22 | Pegasus |
| 23 | Grim Reaper |
| 24 | Kraken |
| 25 | Frankenstein |
| 26 | Cerberus |
| 27 | Griffin |
| 28 | Zombie |
| 29 | Sphynx |
| 30 | Centaur |

## Implementation Notes

The document should stay product-focused, but it is useful to anchor the design to the current codebase.

- Quest routing and progression should live in [application.py](application.py).
- Quest and sidebar payload preparation should live in [helpers.py](helpers.py) or a dedicated content helper.
- The main rendering surfaces are [templates/layout.html](templates/layout.html), [templates/train.html](templates/train.html), [templates/trainset.html](templates/trainset.html), and [templates/quizset.html](templates/quizset.html).
- Any interactive sidebar behavior should be driven from [static/main.js](static/main.js) only after the server has supplied the correct quest state.
- Static UI translation continues through [messages.pot](messages.pot) and the locale catalogs in [translations/en/LC_MESSAGES/messages.po](translations/en/LC_MESSAGES/messages.po) and [translations/he/LC_MESSAGES/messages.po](translations/he/LC_MESSAGES/messages.po).

## Validation and Rollout

Before broad rollout, the content model should pass a small but strict checklist.

- Quest loop wording should appear only once in the doc.
- Sidebar text should clearly read as mirrored state, not independent logic.
- English and Hebrew content files should share the same IDs and structure.
- RTL rendering should be checked for Hebrew.
- Quest titles, story text, quiz prompts, and reward labels should all render correctly in both locales.
- A single pilot quest pack should be tested end to end before adding more content.

## Open Decisions

These choices can stay open until the implementation phase, but the document should call them out clearly.

- Whether the sidebar shows vitals all the time or only during active missions.
- How speech-bubble line selection is prioritized when both episode-level and quest-state lines are available.
- Whether reward names are managed strictly as localized content labels or shared UI/content labels.

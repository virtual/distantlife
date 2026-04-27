
# Event Logging

Logging user and system events enables auditing, debugging, analytics, and support investigations. A centralized event log tracks all meaningful actions across the quest system, pet management, and unlock mechanics.

### Logging Security and Retention

To reduce exposure risk, event logs should follow strict storage, access, and retention rules.

- **Access control**: Restrict log access to authorized admin/support roles only.
- **Access auditing**: Log who viewed or exported logs and when.
- **Data minimization**: Store only required fields for operations and investigations.
- **No secrets in logs**: Never write credentials, tokens, session IDs, or payment details.
- **Redaction**: Sanitize free-text fields (for example admin reasons) to remove personal or sensitive data.
- **Retention**: Define a fixed retention window (for example 90-180 days for operational logs), then purge or archive.
- **User lifecycle cleanup**: On account deletion requests, remove or anonymize user-linked log records according to policy.
- **Environment controls**: Keep production logs separate from development logs.
- **Export controls**: Exports should be permissioned, timestamped, and limited to minimum necessary scope.

### Log Schema

Create an `event_log` table to store all events:

```sql
CREATE TABLE event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    pet_type_id INTEGER,
    quest_id TEXT,
    quest_pack_id TEXT,
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (pet_type_id) REFERENCES pet_types(id)
);
```

### Event Types

**Pet and Adoption Events:**
- `pet_adopted` - User adopted a new pet (fields: pet_type_id, pet_id, pet_name, pet_gender, default_gender)
- `pet_active_changed` - User switched active pet (fields: pet_id, pet_type_id, pet_name, pet_gender)
- `pet_deleted` - Pet was deleted/released (fields: pet_id, pet_type_id, pet_name, pet_gender)

**Pet Unlock Events:**
- `pet_unlocked` - Pet type became available to user (fields: pet_type_id, unlock_reason, unlock_source_id)
- `pet_unlock_attempt_blocked` - User tried to adopt a locked pet (fields: pet_type_id)

**Quest Events:**
- `quest_started` - User began a quest (fields: quest_id, quest_pack_id, quest_line_id, active_pet_id, active_pet_gender)
- `quest_completed` - User finished a quest (fields: quest_id, quest_pack_id, episode_id, time_spent_seconds)
- `quest_access_blocked` - User tried to access a restricted quest (fields: quest_id, active_pet_type_id, allowed_pet_type_ids)

**Learning and Quiz Events:**
- `vocabulary_trained` - User trained words on Train page (fields: set_id, word_count, time_spent_seconds)
- `vocabulary_learned` - User marked vocabulary as learned (fields: set_id, word_count)
- `quiz_attempted` - User took a quiz (fields: quest_id, episode_id, quiz_type, score, time_spent_seconds, passed)

**Reward Events:**
- `reward_earned` - User received a reward (fields: quest_id, reward_type, reward_value, pet_type_id)
- `achievement_unlocked` - User earned an achievement (fields: achievement_id, achievement_name)

**Admin Events:**
- `admin_pet_unlock_forced` - Admin manually unlocked a pet for user (fields: pet_type_id, admin_user_id, reason)
- `admin_pet_reset` - Admin reset pet unlocks to defaults (fields: admin_user_id, reason)
- `admin_quest_triggered` - Admin manually triggered a quest (fields: quest_id, admin_user_id)

### Logging Implementation

Create a helper function to log events:

```python
def log_event(user_id, event_type, pet_type_id=None, quest_id=None, quest_pack_id=None, data=None):
    """
    Log a user or system event.
    
    :param int user_id - user's ID
    :param str event_type - type of event (see Event Types above)
    :param int pet_type_id - optional pet type ID
    :param str quest_id - optional quest ID
    :param str quest_pack_id - optional quest pack ID
    :param dict data - optional extra context as JSON
    """
    db.execute(
        "INSERT INTO event_log (user_id, event_type, pet_type_id, quest_id, quest_pack_id, data) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, event_type, pet_type_id, quest_id, quest_pack_id, json.dumps(data) if data else None)
    )
    con.commit()
```

### When to Log

- **Immediately** after any state change (pet adoption, unlock, quest completion).
- **Before** denying access (blocked unlock attempt, restricted quest access).
- **During** long operations (vocabulary training, quiz attempts) for analytics and debugging.
- **On request** for admin audit trails (manual pet resets, forced unlocks).

### Use Cases

- **Debugging**: Trace user issues by reviewing their event history.
- **Support**: Help users recover lost progress or investigate disputes.
- **Analytics**: Identify popular quests, average completion times, pet adoption patterns.
- **Audit**: Track admin actions for accountability.
- **Reversals**: If a pet unlock was granted by mistake, admin can review the log and undo the entry.
- **Retention**: Understand user journey milestones and engagement funnels.

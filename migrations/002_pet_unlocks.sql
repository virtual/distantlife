-- Pet locking rollout: starter unlocks + per-user unlock table

ALTER TABLE pet_types ADD COLUMN default_unlocked INTEGER NOT NULL DEFAULT 0;

UPDATE pet_types
SET default_unlocked = 1
WHERE id IN (1, 6, 10, 26, 16);

CREATE TABLE IF NOT EXISTS user_pet_unlocks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  pet_type_id INTEGER NOT NULL,
  unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, pet_type_id),
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(pet_type_id) REFERENCES pet_types(id)
);

CREATE INDEX IF NOT EXISTS idx_user_pet_unlocks_user_id ON user_pet_unlocks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_pet_unlocks_pet_type_id ON user_pet_unlocks(pet_type_id);

-- Backfill starter unlocks for existing users.
INSERT INTO user_pet_unlocks (user_id, pet_type_id, unlocked_at)
SELECT u.id, pt.id, CURRENT_TIMESTAMP
FROM users u
JOIN pet_types pt ON pt.default_unlocked = 1
LEFT JOIN user_pet_unlocks upu
  ON upu.user_id = u.id
 AND upu.pet_type_id = pt.id
WHERE upu.id IS NULL;

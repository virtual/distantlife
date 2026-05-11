-- Pet gender rollout: store gender on pets and default gender on pet types

ALTER TABLE pet_types ADD COLUMN default_gender TEXT NOT NULL DEFAULT 'random';
ALTER TABLE pets ADD COLUMN gender TEXT NOT NULL DEFAULT 'neutral';

-- CREATE TABLE users (id INTEGER, username TEXT NOT NULL, hash TEXT NOT NULL, cash NUMERIC NOT NULL DEFAULT 10000.00, PRIMARY KEY(id));
-- CREATE UNIQUE INDEX username ON users (username);


-- CREATE TABLE stocks (id INTEGER, symbol TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY(id));
-- CREATE UNIQUE INDEX symbol ON stocks (symbol);


-- # CREATE TABLE portfolio (trans_id INTEGER, user_id INTEGER NOT NULL, stock_id INTEGER NOT NULL, count INTEGER, transaction_date DATETIME, PRIMARY KEY(trans_id));
-- CREATE TABLE portfolio (trans_id INTEGER, user_id INTEGER NOT NULL, stock_id INTEGER NOT NULL, count INTEGER, transaction_date DATETIME, price_per_share DECIMAL(19, 4), PRIMARY KEY(trans_id));

-- CREATE INDEX user_id ON portfolio (user_id);
-- CREATE INDEX stock_id ON portfolio (stock_id);

-- ALTER TABLE portfolio ADD price_per_share DECIMAL(19, 4);




CREATE TABLE `users` (
  `id` integer,
  `username` varchar(255) NOT NULL,
  `full_name` varchar(255),
  `password` hash,
  `email` varchar(255),
  `created_at` timestamp,
  `last_login` timestamp,
  `preferred_lang` integer,
  `learning_lang` integer,
  `active_pet_id` integer,
  PRIMARY KEY(id)
);
CREATE UNIQUE INDEX username ON users (username);

CREATE TABLE `owners` (
  `id` integer,
  `owner_id` integer,
  `pet_id` integer,
  PRIMARY KEY(id)
);

CREATE TABLE `pets` (
  `id` integer,
  `type` integer,
  `name` varchar(255),
  `created` timestamp,
  `exp` integer,
  PRIMARY KEY(id)
);

CREATE TABLE `pet_types` (
  `id` integer,
  `imgsrc` varchar(255),
  `pet_type` varchar(255),
  `exp_required` integer,
  PRIMARY KEY(id)
);

CREATE TABLE `word_sets` (
  `id` integer,
  `word_id` id,
  `imgsrc` varchar(255),
  PRIMARY KEY(id)
);

CREATE TABLE `words` (
  `id` integer,
  `wordstr` varchar(255),
  `audiopath` varchar(255),
  `language_id` integer,
  `type` integer,
  PRIMARY KEY(id)
);

CREATE TABLE `sets_learned` (
  `id` integer,
  `subject` varchar(255),
  `user_id` integer,
  `wordsets` integer,
  `started` timestamp,
  `completed` timestamp,
  PRIMARY KEY(id)
);

CREATE TABLE `words_learned` (
  `id` integer,
  `user_id` integer,
  `word` integer,
  `sets_learned_id` integer,
  `learned` boolean,
  PRIMARY KEY(id)
);

CREATE TABLE `word_type` (
  `id` integer,
  `type` varchar(255),
  PRIMARY KEY(id)
);

CREATE TABLE `word_translation` (
  `id` integer,
  `orig_lang` id,
  `trans_lang` id,
  `orig_word` id,
  `trans_word` id,
  PRIMARY KEY(id)
);

CREATE TABLE `languages` (
  `id` integer,
  `charcode` varchar(255),
  `dir` varchar(255),
  `name` varchar(255),
  `bodyclass` varchar(255),
  PRIMARY KEY(id)
);




CREATE TABLE `pet_types` (
  `id` integer,
  `imgsrc` varchar(255),
  `pet_type` varchar(255),
  PRIMARY KEY(id)
);


INSERT INTO `pet_types` (imgsrc, pet_type) values ('/pets/pet-wolf.png', 'Wolf');
INSERT INTO `pet_types` (imgsrc, pet_type) values ('/pets/pet-crow.png', 'Crow');
INSERT INTO `pet_types` (imgsrc, pet_type) values ('/pets/pet-gorilla.png', 'Gorilla');



-- ALTER TABLE `pets` ADD FOREIGN KEY (`id`) REFERENCES `owners` (`pet_id`);

-- ALTER TABLE `users` ADD FOREIGN KEY (`id`) REFERENCES `owners` (`owner_id`);

-- ALTER TABLE `pet_types` ADD FOREIGN KEY (`id`) REFERENCES `pets` (`type`);

-- ALTER TABLE `words` ADD FOREIGN KEY (`id`) REFERENCES `word_sets` (`word_id`);

-- ALTER TABLE `words` ADD FOREIGN KEY (`language_id`) REFERENCES `languages` (`id`);

-- ALTER TABLE `words` ADD FOREIGN KEY (`language_id`) REFERENCES `users` (`preferred_lang`);

-- ALTER TABLE `words` ADD FOREIGN KEY (`language_id`) REFERENCES `users` (`learning_lang`);

-- ALTER TABLE `words_learned` ADD FOREIGN KEY (`user_id`) REFERENCES `users` (`id`);

-- ALTER TABLE `words_learned` ADD FOREIGN KEY (`word`) REFERENCES `words` (`id`);

-- ALTER TABLE `words_learned` ADD FOREIGN KEY (`sets_learned_id`) REFERENCES `sets_learned` (`id`);

-- ALTER TABLE `words` ADD FOREIGN KEY (`type`) REFERENCES `word_type` (`id`);

-- ALTER TABLE `word_translation` ADD FOREIGN KEY (`orig_lang`) REFERENCES `languages` (`id`);

-- ALTER TABLE `word_translation` ADD FOREIGN KEY (`trans_lang`) REFERENCES `languages` (`id`);

-- ALTER TABLE `word_translation` ADD FOREIGN KEY (`orig_word`) REFERENCES `words` (`id`);

-- ALTER TABLE `word_translation` ADD FOREIGN KEY (`trans_word`) REFERENCES `words` (`id`);

-- notes
-- pet needs active flag
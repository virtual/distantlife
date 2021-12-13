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

INSERT INTO languages (charcode, dir, name) VALUES ('en', 'ltr', 'English');
INSERT INTO languages (charcode, dir, name) VALUES ('he', 'rtl', 'עברית');




CREATE TABLE `word_set_words` (
  `id` integer,
  `word_set_id` id,
  `word_id` id,
  PRIMARY KEY(id)
);

INSERT INTO word_sets (imgsrc, set_name) VALUES ("/sets/fruits.png", "פרי");

INSERT INTO word_type (type) VALUES ("noun");

INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (2, 1, "Tapuch","תפוח");
INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (2, 1, "Afarsek","אפרסק");
INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (2, 1, "Shezif","שזיפ");
INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (2, 1, "Mango","מנגו");

INSERT INTO word_set_words (word_set_id, word_id) VALUES (1, 1);
INSERT INTO word_set_words (word_set_id, word_id) VALUES (1, 2);
INSERT INTO word_set_words (word_set_id, word_id) VALUES (1, 3);
INSERT INTO word_set_words (word_set_id, word_id) VALUES (1, 4);

INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (1, 1, "a-pl", "Apple");
INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (1, 1, "peech", "Peach");
INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (1, 1, "pluhm", "Plum");
INSERT INTO words (language_id, type, pronunciation, wordstr) VALUES (1, 1, "mang-go", "Mango");

INSERT INTO word_sets (imgsrc, set_name) VALUES ("/sets/fruits.png", "Fruits");
INSERT INTO word_set_words (word_set_id, word_id) VALUES (2, 5);
INSERT INTO word_set_words (word_set_id, word_id) VALUES (2, 6);
INSERT INTO word_set_words (word_set_id, word_id) VALUES (2, 7);
INSERT INTO word_set_words (word_set_id, word_id) VALUES (2, 8);

-- en to he
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (1, 2, 5, 1);
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (1, 2, 6, 2);
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (1, 2, 7, 3);
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (1, 2, 8, 4);

SELECT words.wordstr, words.pronunciation, word_type.type FROM words 
JOIN word_set_words ON word_set_words.word_id = words.id
JOIN word_type ON words.type = word_type.id
where word_set_words.word_set_id = 1;

ALTER TABLE word_sets ADD COLUMN language_id integer;
update word_sets set language_id = 2 WHERE id = 1;
update word_sets set language_id = 1 WHERE id = 2;


UPDATE `pet_types` set imgsrc = '/pets/002-dragon.png', pet_type = 'Dragon', exp_required = 0 where id = 1;
UPDATE `pet_types` set imgsrc = '/pets/004-ufo.png', pet_type = 'UFO', exp_required = 0 where id = 2;
UPDATE `pet_types` set imgsrc = '/pets/005-robot.png', pet_type = 'Robot', exp_required = 0 where id = 3;
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/010-unicorn.png', 'Unicorn', 100);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/011-gnome.png', 'Gnome', 100);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/013-genie.png', 'Genie', 100);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/015-bigfoot.png', 'Bigfoot', 200);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/017-goblin.png', 'Goblin', 200);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/018-oni.png', 'Oni', 200);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/019-faun.png', 'Faun', 300);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/021-medusa.png', 'Medusa', 300);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/024-krampus.png', 'Krampus', 300);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/026-godzilla.png', 'Godzilla', 400);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/027-werewolf.png', 'Werewolf', 400);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/029-haunted.png', 'Haunted', 400);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/030-cyclops.png', 'Cyclops', 500);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/031-frog.png', 'Frog', 500);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/032-ogre.png', 'Ogre', 500);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/033-minotaur.png', 'Minotaur', 600);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/034-jackalope.png', 'Jackalope', 600);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/035-loch-ness-monster.png', 'Loch-ness Monster', 600);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/038-pegasus.png', 'Pegasus', 700);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/040-grim-reaper.png', 'Grim Reaper', 700);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/041-kraken.png', 'Kraken', 700);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/042-frankenstein.png', 'Frankenstein', 800);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/043-cerberus.png', 'Cerberus', 800);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/044-griffin.png', 'Griffin', 800);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/045-zombie.png', 'Zombie', 900);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/047-sphynx.png', 'Sphynx', 900);
INSERT INTO `pet_types` (imgsrc, pet_type, exp_required) values ('/pets/048-centaur.png', 'Centaur', 900);


-- updated table schema 2021/12/05
CREATE TABLE `users` (
  `id` integer,
  `username` varchar(255) NOT NULL,
  `full_name` varchar(255),
  `password` hash,
  `email` varchar(255),
  `created_at` timestamp,
  `last_login` timestamp,
  `preferred_lang` integer,
  `learning_lang` integer, `active_pet_id` integer,
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
  `pet_type` varchar(255), `exp_required` integer,
  PRIMARY KEY(id)
);
CREATE TABLE `word_sets` (
  `id` integer,
  `imgsrc` varchar(255), set_name varchar, language_id integer,
  PRIMARY KEY(id)
);
CREATE TABLE `words` (
  `id` integer,
  `wordstr` varchar(255),
  `audiopath` varchar(255),
  `language_id` integer,
  `type` integer, pronunciation varchar,
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
CREATE TABLE `word_set_words` (
  `id` integer,
  `word_set_id` id,
  `word_id` id,
  PRIMARY KEY(id)
);

CREATE TABLE `word_images` (
  `id` integer,
  `imgsrc` varchar,
  PRIMARY KEY(id)
);

insert into word_images (imgsrc) values ('/words/fruit/apple.png');
insert into word_images (imgsrc) values ('/words/fruit/cherries.png');
insert into word_images (imgsrc) values ('/words/fruit/plums_b.png');
insert into word_images (imgsrc) values ('/words/fruit/tomato.png');
insert into word_images (imgsrc) values ('/words/fruit/berries_05_b.png');
insert into word_images (imgsrc) values ('/words/fruit/peach.png');
insert into word_images (imgsrc) values ('/words/fruit/pomegranate.png');
insert into word_images (imgsrc) values ('/words/fruit/watermelon.png');

SELECT words.wordstr, words.pronunciation, word_type.type, word_images.imgsrc FROM words JOIN word_set_words ON word_set_words.word_id = words.id JOIN word_type ON words.type = word_type.id
JOIN word_images ON words.imgsrc_id = word_images.id where word_set_words.word_set_id = 1

SELECT word_sets.id, words.wordstr, words.id, word_sets.imgsrc FROM word_sets
JOIN words ON word_sets.set_name_word_id = words.id 
WHERE word_sets.language_id = 2;

INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (1, 2, 10, 9);
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (2, 1, 9, 10);


-- he to en missing
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (2, 1, 1, 5);
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (2, 1, 2, 6);
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (2, 1, 3, 7);
INSERT INTO word_translation (orig_lang, trans_lang, orig_word, trans_word) VALUES (2, 1, 4, 8);
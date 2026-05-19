#!/usr/bin/env python3
"""In-place migration for quest story schema.

Converts legacy episode fields:
- story_text -> story_sentences (aligned gender variants)
- Adds required top-level meta block
- Adds sentence_id for cloze questions
- Removes legacy fields story_text, speech_bubble_lines, and sentences
"""

import argparse
import datetime
import json
import re
from pathlib import Path

GENDERS = ("male", "female", "neutral")


def split_sentences(text):
    if not isinstance(text, str):
        return []

    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []

    # Split on sentence boundaries while keeping punctuation attached.
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def build_story_sentences(story_text):
    if not isinstance(story_text, dict):
        return []

    per_gender = {
        gender: split_sentences(story_text.get(gender, ""))
        for gender in GENDERS
    }

    max_len = max((len(values) for values in per_gender.values()), default=0)
    if max_len == 0:
        return []

    story_sentences = []
    neutral_sentences = per_gender.get("neutral", [])

    for idx in range(max_len):
        sentence_obj = {}
        neutral_fallback = neutral_sentences[idx] if idx < len(neutral_sentences) else ""
        sentence_obj["id"] = f"s{idx + 1}"

        for gender in GENDERS:
            values = per_gender.get(gender, [])
            sentence_obj[gender] = values[idx] if idx < len(values) else neutral_fallback

        story_sentences.append(sentence_obj)

    return story_sentences


def prompt_to_regex(prompt_text):
    escaped = re.escape(prompt_text)
    # Support one or more underscore runs as a blank marker.
    escaped = re.sub(r"_+", r".+", escaped)
    return re.compile(rf"^{escaped}$", re.IGNORECASE)


def find_sentence_index(question, resolved_sentences):
    if not resolved_sentences:
        return 0

    existing_idx = question.get("sentence_idx")
    if isinstance(existing_idx, int) and 0 <= existing_idx < len(resolved_sentences):
        return existing_idx

    answer = str(question.get("answer", "")).strip().lower()

    # Try prompt matching first when available.
    prompt = question.get("prompt")
    prompt_candidates = []
    if isinstance(prompt, str) and prompt.strip():
        prompt_candidates.append(prompt.strip())
    elif isinstance(prompt, dict):
        for gender in GENDERS:
            value = prompt.get(gender)
            if isinstance(value, str) and value.strip():
                prompt_candidates.append(value.strip())

    for prompt_text in prompt_candidates:
        regex = prompt_to_regex(prompt_text)
        for idx, sentence in enumerate(resolved_sentences):
            if regex.match(sentence):
                return idx

    # Fall back to first sentence containing answer text.
    if answer:
        for idx, sentence in enumerate(resolved_sentences):
            if answer in sentence.lower():
                return idx

    return 0


def migrate_file(path):
    with path.open("r", encoding="utf-8") as file_obj:
        quest = json.load(file_obj)

    quest["meta"] = {
        "schema_version": "1.0.0",
        "generator": "quest_pipeline_v1",
        "generated_at": datetime.datetime.utcnow().isoformat(),
    }

    migrated_episodes = 0

    for episode in quest.get("episodes", []):
        story_sentences = episode.get("story_sentences")

        if not isinstance(story_sentences, list) or not story_sentences:
            story_sentences = build_story_sentences(episode.get("story_text"))
            episode["story_sentences"] = story_sentences

        for idx, sentence in enumerate(episode.get("story_sentences", []), start=1):
            if isinstance(sentence, dict):
                sentence["id"] = sentence.get("id") or f"s{idx}"

        # Resolve neutral sentence text list for sentence_id inference.
        resolved_sentences = []
        sentence_ids = []
        for idx, sentence in enumerate(episode.get("story_sentences", []), start=1):
            if isinstance(sentence, dict):
                resolved = sentence.get("neutral") or sentence.get("male") or sentence.get("female") or ""
                resolved_sentences.append(str(resolved))
                sentence_ids.append(sentence.get("id") or f"s{idx}")
            else:
                resolved_sentences.append(str(sentence))
                sentence_ids.append(f"s{idx}")

        questions = episode.get("quiz", {}).get("questions", [])
        if isinstance(questions, list):
            for question in questions:
                if not isinstance(question, dict):
                    continue
                if question.get("type") == "cloze":
                    sentence_idx = find_sentence_index(question, resolved_sentences)
                    sentence_id = sentence_ids[sentence_idx] if sentence_ids else "s1"
                    question["sentence_id"] = sentence_id
                    question.pop("sentence_idx", None)

        episode.pop("story_text", None)
        episode.pop("speech_bubble_lines", None)
        episode.pop("sentences", None)
        migrated_episodes += 1

    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(quest, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")

    return migrated_episodes


def main():
    parser = argparse.ArgumentParser(description="In-place migrate quests to story_sentences schema")
    parser.add_argument(
        "--root",
        default="quests",
        help="Root quest directory containing locale subfolders (default: quests)",
    )
    args = parser.parse_args()

    root = Path(args.root)
    nested_files = list(root.glob("*/*.json"))
    flat_files = list(root.glob("*.json"))
    quest_files = sorted({*nested_files, *flat_files})

    if not quest_files:
        print(f"No quest files found under {root}")
        return

    total_episodes = 0
    for path in quest_files:
        migrated_episodes = migrate_file(path)
        total_episodes += migrated_episodes
        print(f"Migrated {path} ({migrated_episodes} episode(s))")

    print(f"Done. Migrated {len(quest_files)} file(s), {total_episodes} episode(s).")


if __name__ == "__main__":
    main()

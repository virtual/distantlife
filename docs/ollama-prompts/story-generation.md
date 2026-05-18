# 1. Define your core data variables
level = "CEFR A2"
character_name = "Faun"
animal_type = "faun"
gender = "Male"
quest_name = "garden_adventure"

# 2. Add story guidance variables
story_title = "יום הגינון של פאון (Faun's Gardening Day)"
story_overview = (
    "Faun has a strong רָעָב (hunger) for a sweet, crunchy treat. "
    "He decides to become a gardener for a day, taking a סַל (basket) "
    "of tools out to the sunny גַּן (garden). He carefully buries a small "
    "זֶרַע (seed) in the dirt, waters it, and proudly harvests his very "
    "first home-grown גֶּזֶר (carrot)."
)

# 3. Keep your vocabulary words in a clean Python list
word_list = [
    "רָעָב (hunger/hungry)",
    "סַל (basket)",
    "גַּן (garden)",
    "זֶרַע (seed)",
    "גֶּזֶר (carrot)"
]

# Format the word list for the prompt
formatted_words = "\n".join([f"- {word}" for word in word_list])

# 4. Construct the dynamic prompt using an f-string
large_prompt = f"""
You are an expert L2 Hebrew teacher and curriculum designer. Your task is to write a short, Hebrew-only beginner-level (CEFR {level}) educational story about a virtual pet.

Story Metadata:
- Requested Title: {story_title}
- Plot Overview to Follow: {story_overview}

Main Character Details:
- Name: {character_name}
- Type of animal: {animal_type}
- Gender: {gender} (Ensure all Hebrew verbs and adjectives describing the character match this grammatical gender).

Mandatory Vocabulary to Include:
{formatted_words}

Formatting & Rules:
- {character_name} is a {gender} pet. Therefore, all Hebrew verbs, pronouns, and adjectives describing {character_name} must use the {gender} singular present tense form.
- The language level must be strictly {level} Hebrew: short sentences, present and past tense only
- Do not explain grammar or add any extra text to the story, aside from the story text itself.
- Write the Hebrew story FIRST. Let your attention focus on natural Hebrew syntax.
- Closely follow the narrative steps provided in the Plot Overview, ensuring the story flows naturally for a {level} learner.
- CRITICAL: Do not write English words, translations, or phonetic guides inside the Hebrew text. No parentheses, no brackets, and no mixed-alphabet words (like "zֶרַע"). The Hebrew story must contain ONLY clean, valid Hebrew characters.
- Do not create any other names, use nouns only (bird, girl, city, etc)
"""

# Generate the unique timestamped filepath
# Format: YYYYMMDD_HHMMSS (e.g., 20260518_135249_faun_garden_adventure.md)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
safe_name = character_name.lower().replace(" ", "_")
filename = f"{timestamp}_{safe_name}_{quest_name}.md"

# Run the automation
save_ai_story(
    prompt=large_prompt,
    filepath = f"../distantlife/app/static/quests/{filename}"
)
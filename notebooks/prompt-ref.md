# Prompt references

## English Generation Prompt Template

```py
You are an expert children's book author. Write an original, charming short story in simple, clear English based on this plot overview: 
"{story_overview}"

Character Profiles & Genders:
1. Protagonist: "{character_name}" (the pet). 
   - CRITICAL: "{character_name}"'s gender is dynamic. For this generation run, "{character_name}" is "{gender}". 
   All verbs, pronouns, and adjectives describing "{character_name}"'s actions must strictly conform to grammar rules.
2. Auxiliary Character: "Adva" (the gardener).
   - GENDER: Static Female. All verbs, pronouns, and adjectives describing Adva's actions must ALWAYS 
   remain in the feminine singular (e.g., הלכה, אמרה, שלה). This must NOT change regardless of the Protagonist's active gender.

Rules:
- Keep the sentences short and clear so they translate cleanly into early-intermediate language structures.
- Do not create any other names, use nouns only (bird, girl, city, etc).
- Do not explain grammar or add any extra text to the story, aside from the story text itself.
- Do not format any text in the story aside from using new lines.
```


------------------

## Hebrew Translation Prompt Template

```py
- Rewrite this story using {gender} grammatical agreement throughout.  

Story:
{base_story}
"""
    
# Construct the dynamic Hebrew translation prompt, feeding it the English text
large_prompt_he = f"""
You are an expert bilingual translator fluent in both English and Hebrew. 

Translate the following English story into grammatically correct, natural Hebrew suitable for a CEFR A1/A2 language learner. 

English Story to Translate:
\"\"\"
{english_story_output}
\"\"\"

Rules for the translation:
- Do NOT use vowel points (nikkud) at all. Write in clean, modern, unpointed Hebrew text (Ktav Male).
- Ensure strict gender agreement (since the main character {character_name} is {gender}, use proper masculine verb inflections and adjectives).
- Match the key concepts exactly to these Hebrew vocabulary items:
{formatted_words}
- Do not explain grammar, do not add conversational notes, and do not include the original English in your output. Return ONLY the Hebrew translation.

CRITICAL OUTPUT FORMATTING RULES:
- Return structured output only using a direct Hebrew translation.
- DO NOT include introductory remarks like "Here is the translation...".
- DO NOT include conversational text, pleasantries, or explanations.
- Start your response directly with the translated Hebrew title or the first line of the translated story text.
- Match the new lines from the English version.
- Do not let the gender of the protagonist influence or mutate the grammatical gender of other characters. 
  Keep their linguistic "coreference chains" completely separate and independent.
```

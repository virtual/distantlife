# Developer Requirements: Quiz Refactoring

## Overview
Refactor the existing monolithic "Quiz Page" into a multi-step, sequential "Recall-Check" workflow. This transition aims to reduce cognitive load, enforce active recall, and facilitate better learning outcomes for A2-level Hebrew learners.

## 1. Core Architecture: Multi-Step Wizard
* **Sequential Navigation:** Break the quiz into a series of individual steps. Only one step is visible at a time.
* **Progress Tracking:** Implement a global progress bar at the top of the UI, reflecting the total of 10 questions/tasks.
* **Step Logic:** Each step must be a self-contained unit combining one segment of the story context with its corresponding task (Sentence Building or Comprehension Question).

## 2. The "Recall-Check" Workflow (Error-Correction Logic)
The system must enforce active recall by keeping the source content hidden by default.

### A. The Challenge Phase
* The sentence/question task is presented.
* No more than 10 questions/tasks should be presented in total, with a mix of sentence building and comprehension questions.
* Quiz questions and sentence building should be randomized in order to prevent pattern recognition and encourage genuine recall.
* The source story segment is **hidden**.
* The user performs the task (drag-and-drop or selection).

### B. The Verification Phase
* **User Action:** User clicks "Submit."
* **If Correct:** Display positive feedback (masculine-gendered phrasing: "כָּל הַכָּבוֹד!"). Update the progress bar and enable the "Next" button.
* **If Incorrect:** * Disable the final "Submit" logic for this attempt.
    * Display a "Review Context" (See Hint) button.
    * **Reveal:** Upon clicking, the relevant story segment fades into view, with new/difficult vocabulary highlighted (if applicable).
    * **Retry:** Allow the user to reset the task and attempt the construction again.

## 3. UI/UX Specifications
* **Minimalist Interface:** Remove all extraneous content. Keep the focus on the current task.
* **Nikkud Handling:** * Ensure **nǐkkūd** is applied **only to new vocabulary**.
    * Standard A1/A2 words remain plain text to foster reading fluency.
* **Persistent UI Elements:**
    * Progress Bar (Top)
    * "Back" Button (To allow navigation to previous steps/segments).
    * "Review Context" / "Hint" Button (Only available post-incorrect attempt).
* **Responsive Design:** Ensure the wizard layout is optimized for mobile and desktop, specifically ensuring drag-and-drop elements remain accessible.

## 4. Technical Implementation Notes
* **State Management:** Track `current_step` (0-9) to handle the display of segments and quiz items.
* **Feedback/Correction Language:** All system messages must be in masculine-gendered Hebrew (e.g., "אַתָּה צוֹדֵק").
* **Error Correction Notation:** If the system provides feedback on incorrect Hebrew input, use the arrow notation (e.g., `Incorrect Input` → `Correct Hebrew Word`).

## 5. Summary of Workflow
1.  **Read:** (Implicitly managed by previous steps or revealed context)
2.  **Interact:** Build/Answer.
3.  **Validate:** Immediate feedback.
4.  **Reflect:** (If needed) Reveal story segment as a "lifeline."
5.  **Advance:** Proceed to the next index in the sequence.

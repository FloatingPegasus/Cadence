# Cadence

**Cadence** is a streamlined habit-tracking system designed to help users define goals, log daily actions, and build long-term consistency through visual accountability.

---

## 1. What is Cadence?
Cadence provides a structured environment for behavioral change. It focuses on the core mechanics of habit formation: **definition, action, and repetition.**

## 2. What V1 Includes
V1 focuses on a "zero-friction" logging experience:
* **Monthly Grid Interface:** A high-level view of your habits across the month.
* **Instant Logging:** One-click tracking to record completions.
* **Daily Summaries:** Quick snapshots of your performance.

## 3. Out of Scope (V1)
To keep the initial release lean, V1 **explicitly does NOT** include:
* Advanced data visualizations (charts or graphs).
* Deep behavioral analysis or trend reporting.

## 4. Tech Stack
* **Backend:** Flask
* **Database:** SQLAlchemy
* **Styling:** CSS & Bootstrap

---

## 5. App Flow
The user journey follows a simple, linear path:

1. **Login:** User enters their private dashboard.
2. **The Grid:** The app displays a calendar-style grid (Habits as **rows**, Dates as **columns**).
3. **Management:** User adds their specific habits to the list.
4. **Logging:** User clicks the checkbox on the specific day when a habit is completed.

> **Note:** V1 is designed for speed and simplicity over complex analysis.
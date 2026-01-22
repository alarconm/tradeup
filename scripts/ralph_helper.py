#!/usr/bin/env python3
"""
Ralph Helper - Finds next story and prepares prompts for the batch runner.

Usage:
    python scripts/ralph_helper.py next    # Get next story info and create prompt
    python scripts/ralph_helper.py mark    # Mark current story as complete
    python scripts/ralph_helper.py status  # Show current progress
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

WORKING_DIR = Path(__file__).parent.parent.absolute()
ROADMAP_DIR = WORKING_DIR / "roadmap" / "epics"
PROGRESS_FILE = WORKING_DIR / "progress.txt"
LOG_FILE = WORKING_DIR / "ralph-run.log"
CURRENT_STORY_FILE = WORKING_DIR / ".ralph-current-story.json"
PROMPT_FILE = WORKING_DIR / ".ralph-current-prompt.txt"

# PRD priority order
PRD_PRIORITY = [
    "06-code-quality-fixes",
    "11-review-collection",
    "07-gamification-system",
    "08-anniversary-rewards",
    "09-nudges-reminders",
    "10-loyalty-page-builder",
    "12-widget-builder",
    "13-ai-trade-in-pricing",
    "01-test-coverage",
    "02-performance-optimization",
    "03-api-documentation",
    "04-monitoring-observability",
    "05-developer-experience",
]


def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")
    print(log_line)


def load_prd(prd_name: str) -> dict | None:
    prd_path = ROADMAP_DIR / prd_name / "prd.json"
    if not prd_path.exists():
        return None
    with open(prd_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_prd(prd_name: str, prd_data: dict):
    prd_path = ROADMAP_DIR / prd_name / "prd.json"
    with open(prd_path, "w", encoding="utf-8") as f:
        json.dump(prd_data, f, indent=2)


def find_next_story() -> tuple[str, dict, int] | None:
    for prd_name in PRD_PRIORITY:
        prd = load_prd(prd_name)
        if not prd:
            continue
        for i, story in enumerate(prd.get("userStories", [])):
            if not story.get("passes", False):
                return (prd_name, story, i)
    return None


def get_progress() -> tuple[int, int]:
    completed = 0
    total = 0
    for prd_name in PRD_PRIORITY:
        prd = load_prd(prd_name)
        if not prd:
            continue
        for story in prd.get("userStories", []):
            total += 1
            if story.get("passes", False):
                completed += 1
    return completed, total


def build_prompt(prd_name: str, story: dict, prd: dict) -> str:
    criteria = "\n".join(f"  - {c}" for c in story.get("acceptanceCriteria", []))
    return f"""You are completing a user story from the TradeUp PRD.

## PRD: {prd.get('title', prd_name)}
Branch: {prd.get('branch', 'main')}

## Story: {story['id']} - {story['title']}
{story.get('description', '')}

### Acceptance Criteria
{criteria}

## Your Task
1. Implement this story completely
2. Follow all acceptance criteria
3. Run relevant tests to verify (pytest for backend, npm test for frontend)
4. Update progress.txt with what you did (append to the file)
5. Commit your changes with message: "feat: {story['id']} - {story['title']}"

## Important Notes
- Work autonomously - do not ask questions
- Make reasonable decisions when requirements are ambiguous
- If tests fail, fix them before committing
- Keep the implementation simple and focused

Begin implementing now.
"""


def cmd_next():
    """Find next story and create prompt file."""
    result = find_next_story()

    if not result:
        print("ALL_COMPLETE")
        return

    prd_name, story, story_index = result
    prd = load_prd(prd_name)
    completed, total = get_progress()

    # Save current story info for mark command
    with open(CURRENT_STORY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "prd_name": prd_name,
            "story_id": story["id"],
            "story_index": story_index,
            "story_title": story["title"]
        }, f)

    # Create prompt file
    prompt = build_prompt(prd_name, story, prd)
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(prompt)

    log(f"Progress: {completed}/{total} ({100*completed//total}%)")
    log(f"Next: {story['id']} - {story['title']} (from {prd_name})")

    # Output for batch script
    print(f"STORY:{story['id']}")
    print(f"PRD:{prd_name}")
    print(f"PROGRESS:{completed}/{total}")


def cmd_mark():
    """Mark current story as complete."""
    if not CURRENT_STORY_FILE.exists():
        print("ERROR: No current story found")
        return

    with open(CURRENT_STORY_FILE, "r", encoding="utf-8") as f:
        info = json.load(f)

    prd_name = info["prd_name"]
    story_index = info["story_index"]
    story_id = info["story_id"]

    prd = load_prd(prd_name)
    if prd and story_index < len(prd.get("userStories", [])):
        prd["userStories"][story_index]["passes"] = True
        save_prd(prd_name, prd)
        log(f"Marked {story_id} as complete")
        print(f"MARKED:{story_id}")
    else:
        print(f"ERROR: Could not find story {story_id}")


def cmd_status():
    """Show current progress."""
    completed, total = get_progress()
    pct = 100 * completed // total if total > 0 else 0
    print(f"Progress: {completed}/{total} stories ({pct}%)")

    result = find_next_story()
    if result:
        prd_name, story, _ = result
        print(f"Next story: {story['id']} - {story['title']}")
        print(f"From PRD: {prd_name}")
    else:
        print("All stories complete!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ralph_helper.py [next|mark|status]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "next":
        cmd_next()
    elif cmd == "mark":
        cmd_mark()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

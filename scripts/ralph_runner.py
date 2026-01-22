#!/usr/bin/env python3
"""
Ralph Autonomous Runner - Runs Claude sessions to complete PRD stories one by one.

Usage:
    python scripts/ralph_runner.py [--max-iterations N] [--dry-run]

This script:
1. Reads all PRD files from roadmap/epics/
2. Finds the first incomplete story (passes: false)
3. Spawns a Claude session to complete that story
4. Updates the PRD and progress.txt when done
5. Repeats until all stories complete or max iterations reached
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
import argparse

# Configuration
WORKING_DIR = Path(__file__).parent.parent.absolute()
ROADMAP_DIR = WORKING_DIR / "roadmap" / "epics"
PROGRESS_FILE = WORKING_DIR / "progress.txt"
LOG_FILE = WORKING_DIR / "ralph-run.log"

# PRD priority order (from CLAUDE.md)
PRD_PRIORITY = [
    "06-code-quality-fixes",      # Phase 1 - Pre-Launch
    "11-review-collection",       # Phase 1 - Pre-Launch
    "07-gamification-system",     # Phase 2 - Competitive Parity
    "08-anniversary-rewards",     # Phase 2 - Competitive Parity
    "09-nudges-reminders",        # Phase 2 - Competitive Parity
    "10-loyalty-page-builder",    # Phase 2 - Competitive Parity
    "12-widget-builder",          # Phase 3 - Differentiation
    "13-ai-trade-in-pricing",     # Phase 3 - Differentiation
    "01-test-coverage",           # Existing (lower priority)
    "02-performance-optimization",
    "03-api-documentation",
    "04-monitoring-observability",
    "05-developer-experience",
]


def log(message: str, also_print: bool = True):
    """Log message to file and optionally print."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    if also_print:
        print(log_line)


def load_prd(prd_name: str) -> dict | None:
    """Load a PRD JSON file."""
    prd_path = ROADMAP_DIR / prd_name / "prd.json"
    if not prd_path.exists():
        return None

    with open(prd_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_prd(prd_name: str, prd_data: dict):
    """Save a PRD JSON file."""
    prd_path = ROADMAP_DIR / prd_name / "prd.json"
    with open(prd_path, "w", encoding="utf-8") as f:
        json.dump(prd_data, f, indent=2)


def find_next_story() -> tuple[str, dict, int] | None:
    """Find the next incomplete story across all PRDs.

    Returns:
        tuple of (prd_name, story_dict, story_index) or None if all complete
    """
    for prd_name in PRD_PRIORITY:
        prd = load_prd(prd_name)
        if not prd:
            continue

        for i, story in enumerate(prd.get("userStories", [])):
            if not story.get("passes", False):
                return (prd_name, story, i)

    return None


def get_total_progress() -> tuple[int, int]:
    """Get total progress across all PRDs.

    Returns:
        tuple of (completed, total)
    """
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


def build_story_prompt(prd_name: str, story: dict, prd: dict) -> str:
    """Build the prompt for Claude to complete a story."""
    criteria_list = "\n".join(f"  - {c}" for c in story.get("acceptanceCriteria", []))

    return f"""You are completing a user story from the TradeUp PRD.

## PRD: {prd.get('title', prd_name)}
Branch: {prd.get('branch', 'main')}

## Story: {story['id']} - {story['title']}
{story.get('description', '')}

### Acceptance Criteria
{criteria_list}

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

When you have completed all acceptance criteria and committed, output exactly:
<story-complete>{story['id']}</story-complete>

If you cannot complete the story due to blockers, output:
<story-blocked>{story['id']}: reason</story-blocked>
"""


def run_claude_session(prompt: str, story_id: str, timeout_minutes: int = 30) -> tuple[bool, str]:
    """Run a Claude Code session with the given prompt.

    Returns:
        tuple of (success: bool, output: str)
    """
    try:
        # Write prompt to temp file for the session
        prompt_file = WORKING_DIR / ".ralph-current-prompt.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Session output file
        output_file = WORKING_DIR / f".ralph-output-{story_id}.txt"

        log(f"Running Claude session for {story_id} (timeout: {timeout_minutes}min)...")
        log(f"Prompt saved to: {prompt_file}")

        # Run Claude Code with the prompt
        # Using stdin to pass the prompt, --dangerously-skip-permissions auto-approves tools
        cmd = ["claude", "--dangerously-skip-permissions"]

        # Use Popen for better control, pass prompt via stdin
        process = subprocess.Popen(
            cmd,
            cwd=str(WORKING_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Send prompt via stdin
        process.stdin.write(prompt)
        process.stdin.close()

        output_lines = []
        start_time = time.time()

        # Read output with timeout
        while True:
            # Check timeout
            if time.time() - start_time > timeout_minutes * 60:
                process.kill()
                log(f"Session timed out after {timeout_minutes} minutes")
                return False, "TIMEOUT"

            # Check if process ended
            if process.poll() is not None:
                break

            # Try to read a line (with select/timeout would be better but keeping simple)
            try:
                line = process.stdout.readline()
                if line:
                    output_lines.append(line)
                    # Log key progress indicators
                    lower_line = line.lower()
                    if any(x in lower_line for x in ["complete", "success", "commit", "error", "fail"]):
                        log(f"  > {line.strip()[:120]}")
            except Exception:
                break

            time.sleep(0.05)

        # Get remaining output
        try:
            remaining, _ = process.communicate(timeout=10)
            if remaining:
                output_lines.append(remaining)
        except subprocess.TimeoutExpired:
            process.kill()

        output = "".join(output_lines)

        # Save output to file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)

        return_code = process.returncode
        log(f"Session ended with exit code: {return_code}")

        # Check for completion markers
        if "<story-complete>" in output:
            log(f"Story {story_id} marked complete!")
            return True, output
        elif "<story-blocked>" in output:
            log(f"Story blocked: {output[-500:]}")
            return False, output
        else:
            # Check return code - 0 means successful execution
            if return_code == 0:
                log(f"Session completed successfully")
                return True, output
            else:
                log(f"Session failed with return code {return_code}")
                # Log last part of output for debugging
                if len(output) > 200:
                    log(f"Last 200 chars: {output[-200:]}")
                return False, output

    except subprocess.TimeoutExpired:
        log(f"Session timed out after {timeout_minutes} minutes")
        return False, "TIMEOUT"
    except FileNotFoundError:
        log("ERROR: 'claude' command not found. Make sure Claude Code CLI is installed and in PATH.")
        return False, "CLAUDE_NOT_FOUND"
    except Exception as e:
        log(f"Session error: {type(e).__name__}: {e}")
        return False, str(e)


def mark_story_complete(prd_name: str, story_index: int):
    """Mark a story as complete in the PRD file."""
    prd = load_prd(prd_name)
    if prd and story_index < len(prd.get("userStories", [])):
        prd["userStories"][story_index]["passes"] = True
        save_prd(prd_name, prd)
        log(f"Marked {prd['userStories'][story_index]['id']} as complete in prd.json")


def main():
    parser = argparse.ArgumentParser(description="Ralph Autonomous Runner")
    parser.add_argument("--max-iterations", type=int, default=100,
                        help="Maximum number of stories to process (default: 100)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without running")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Timeout per story in minutes (default: 30)")
    args = parser.parse_args()

    log("=" * 60)
    log("Ralph Autonomous Runner Starting")
    log(f"Max iterations: {args.max_iterations}")
    log(f"Working directory: {WORKING_DIR}")
    log("=" * 60)

    completed_count = 0
    failed_count = 0

    for iteration in range(1, args.max_iterations + 1):
        # Find next story
        result = find_next_story()

        if not result:
            log("All stories complete! Ralph is done.")
            break

        prd_name, story, story_index = result
        completed, total = get_total_progress()

        log("-" * 40)
        log(f"Iteration {iteration}/{args.max_iterations}")
        log(f"Progress: {completed}/{total} stories complete ({100*completed//total}%)")
        log(f"PRD: {prd_name}")
        log(f"Story: {story['id']} - {story['title']}")
        log("-" * 40)

        if args.dry_run:
            log("DRY RUN: Would process this story")
            continue

        # Load full PRD for context
        prd = load_prd(prd_name)

        # Build prompt
        prompt = build_story_prompt(prd_name, story, prd)

        # Run Claude session
        success, output = run_claude_session(prompt, story['id'], timeout_minutes=args.timeout)

        if success:
            # Mark story as complete
            mark_story_complete(prd_name, story_index)
            completed_count += 1
            log(f"Story {story['id']} completed successfully!")
        else:
            failed_count += 1
            log(f"Story {story['id']} failed - will retry on next run")
            # On failure, wait a bit before continuing
            time.sleep(10)

        # Brief pause between iterations
        time.sleep(5)

    # Final summary
    log("=" * 60)
    log("Ralph Run Complete")
    log(f"Completed: {completed_count} stories")
    log(f"Failed: {failed_count} stories")
    completed, total = get_total_progress()
    log(f"Overall Progress: {completed}/{total} ({100*completed//total}%)")
    log("=" * 60)


if __name__ == "__main__":
    main()

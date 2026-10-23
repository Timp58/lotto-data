#!/usr/bin/env python3
"""
update_lotto.py
Fetches UK National Lottery XML, converts it to latest_lottery_draw.csv,
and commits/pushes changes to the dedicated repository.
"""

import csv
import logging
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import requests

REPO_DIR = Path(__file__).resolve().parent
CSV_PATH = REPO_DIR / "latest_lottery_draw.csv"
LOG_PATH = REPO_DIR / "update_lotto.log"

LOTTO_XML_URL = "https://www.national-lottery.co.uk/results/lotto/draw-history/xml"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

FIELDNAMES = [
    "DrawNumber", "DrawDate", "Ball 1", "Ball 2", "Ball 3",
    "Ball 4", "Ball 5", "Ball 6", "Bonus Ball", "Ball Set",
    "Draw Machine", "Rollover", "Rollover Count", "Next Estimated Jackpot"
]

def fetch_and_convert():
    logging.info("Downloading XML from National Lottery...")
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(LOTTO_XML_URL, headers=headers, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as err:
        logging.error("Failed to download or parse XML: %s", err)
        sys.exit(1)

    rows = []
    for game in root.findall(".//game"):
        draw_elem = game.find("draw")
        draw_num = draw_elem.findtext("draw-number", default="") if draw_elem is not None else ""
        draw_date = draw_elem.findtext("draw-date", default="") if draw_elem is not None else ""

        machines = [m.text for m in draw_elem.findall("draw-machine") if m.text] if draw_elem is not None else []
        machine = machines[0] if machines else ""

        rollover = game.findtext("rollover", default="")
        rollover_count = game.findtext("rollover-count", default="")
        jackpot = game.findtext("next-estimated-jackpot", default="")

        for balls_elem in game.findall("balls"):
            ball_set = balls_elem.findtext("set", default="")
            balls = {}
            for b in balls_elem.findall("ball"):
                idx = b.attrib.get("number")
                if idx:
                    balls[f"Ball {idx}"] = b.text.strip() if b.text else ""

            bonus = balls_elem.findtext("bonus-ball", default="")
            rows.append({
                "DrawNumber": draw_num,
                "DrawDate": draw_date,
                "Ball 1": balls.get("Ball 1", ""),
                "Ball 2": balls.get("Ball 2", ""),
                "Ball 3": balls.get("Ball 3", ""),
                "Ball 4": balls.get("Ball 4", ""),
                "Ball 5": balls.get("Ball 5", ""),
                "Ball 6": balls.get("Ball 6", ""),
                "Bonus Ball": bonus,
                "Ball Set": ball_set,
                "Draw Machine": machine,
                "Rollover": rollover,
                "Rollover Count": rollover_count,
                "Next Estimated Jackpot": jackpot
            })

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    logging.info("Saved %d records to %s", len(rows), CSV_PATH)

def git_commit_and_push():
    def run_git(args):
        return subprocess.run(
            ["git", "-C", str(REPO_DIR)] + args,
            capture_output=True,
            text=True,
            check=False
        )

    # 1. Pull latest changes first to keep local branch in sync with remote
    pull = run_git(["pull", "--rebase", "origin", "main"])
    if pull.returncode != 0:
        logging.error("Git pull failed: %s", pull.stderr)
        return

    # 2. Stage changes
    run_git(["add", str(CSV_PATH)])
    diff = run_git(["diff", "--staged", "--quiet"])

    if diff.returncode == 0:
        logging.info("No changes to CSV detected.")
        return

    # 3. Commit
    commit = run_git(["commit", "-m", "chore: update latest_lottery_draw.csv"])
    if commit.returncode != 0:
        logging.error("Git commit failed: %s", commit.stderr)
        return

    # 4. Push
    push = run_git(["push", "-u", "origin", "main"])
    if push.returncode == 0:
        logging.info("Git push succeeded.")
    else:
        logging.error("Git push failed: %s", push.stderr)
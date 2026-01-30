"""
Core logic for arranging commit dates.
"""

import logging
import random
import datetime
from typing import List, Optional, Dict
import dateutil.parser
import pytz

from .git_utils import GitRepo, GitError

logger = logging.getLogger(__name__)


def calculate_schedule(
    repo: GitRepo,
    commits: List[Dict],
    start_date: datetime.date,
    end_date: datetime.date,
    start_time: str,
    end_time: str,
    timezone_str: Optional[str],
    skip_weekends: bool,
) -> Dict[str, str]:
    """
    Calculate a new schedule for the given commits.

    Args:
        repo: GitRepo instance
        commits: List of commit dictionaries
        start_date: Start date for the range
        end_date: End date for the range
        start_time: Daily start time (HH:MM)
        end_time: Daily end time (HH:MM)
        timezone_str: Timezone string (e.g. "UTC"). If None or empty, uses local system timezone.
        skip_weekends: Whether to skip weekends

    Returns:
        Dictionary mapping commit hash to new ISO 8601 date string
    """
    # 1. Parse times
    try:
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
    except ValueError:
        raise ValueError("Invalid time format. Use HH:MM")

    # Handle Timezone
    if not timezone_str or timezone_str.lower() in ("local", "none", ""):
        tz = dateutil.tz.tzlocal()
    else:
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            # Fallback to dateutil which handles more formats/abbreviations sometimes
            tz = dateutil.tz.gettz(timezone_str)
            if not tz:
                # If still failing, try to see if it's a local abbreviation passed by datetime (like PKT)
                # In this case simpler to warn and use UTC or Local?
                # Let's default to local if matching current system tz name
                local_now = datetime.datetime.now().astimezone()
                if local_now.tzname() == timezone_str:
                    tz = local_now.tzinfo
                else:
                    raise ValueError(f"Unknown timezone: {timezone_str}")

    # 2. Generate valid time slots
    valid_days = []
    current_date = start_date
    while current_date <= end_date:
        if skip_weekends and current_date.weekday() >= 5:  # 5=Sat, 6=Sun
            current_date += datetime.timedelta(days=1)
            continue

        valid_days.append(current_date)
        current_date += datetime.timedelta(days=1)

    if not valid_days:
        raise ValueError("No valid days found in the specified range (check weekends/dates)")

    # 3. Analyze commits (size) to determine weights
    # We need to get commit stats (lines changed) for "size"
    # standard "git log" doesn't give stats easily in one go without parsing --stat
    # For now, we will approximate size or fetch it.
    # Let's simple use 1 as base weight + random factor for now, or assume 'size' is passed if we improved get_commit_info
    # To properly implement "based on total commits sizes", we'd need `git log --numstat` or similar.
    # Let's iterate and get stats.

    commit_weights = []
    total_weight = 0

    logger.info("Analyzing commit sizes...")
    for commit in commits:
        # Get stats: git show --numstat --format="" <hash>
        # Sum of additions + deletions
        result = repo._run_command(
            ["git", "show", "--numstat", "--format=", commit["hash"]], check=False
        )
        size = 0
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        add = int(parts[0]) if parts[0] != "-" else 0
                        delete = int(parts[1]) if parts[1] != "-" else 0
                        size += add + delete
                    except ValueError:
                        pass

        # Avoid 0 size
        weight = max(1, size)
        commit_weights.append((commit, weight))
        total_weight += weight

    # 4. Distribute commits
    # We want to preserve sequence.
    # Commits must remain in order: C_oldest -> C_newest
    # So C_oldest gets the earliest dates, C_newest gets the latest.

    # We can distribute the "total weight" along the "total available seconds".
    # But exact seconds mapping is hard.
    # Simpler approach:
    # 1. Divide the total time range into N buckets (N=total_weight).
    # 2. Assign commits to buckets based on their weight.
    # 3. Randomize time within the assigned day/window.

    # Let's try a continuous time mapping approach.
    # Total available duration in seconds = num_days * (end_time_sec - start_time_sec)

    day_duration_sec = (eh * 3600 + em * 60) - (sh * 3600 + sm * 60)
    if day_duration_sec <= 0:
        raise ValueError("End time must be after start time")

    total_duration_sec = len(valid_days) * day_duration_sec

    # Commits are ordered Newest First usually from git log, but we need Oldest First for timeline
    # commits list should be sorted by original date or just reverse the input if it's from git log
    # Let's assume input 'commits' is ordered Newest First (standard git log).
    # We need to process them Oldest First to assign earliest dates.
    ordered_commits_weights = list(reversed(commit_weights))

    schedule = {}

    current_cumulative_weight = 0

    # Add some randomness to the timeline distribution so it's not perfectly linear
    # We can perturb the weight slightly? Or just pick random time in the target window.

    for commit, weight in ordered_commits_weights:
        # Determine strict range for this commit based on weight
        # range_start_ratio = current_cumulative_weight / total_weight
        # range_end_ratio = (current_cumulative_weight + weight) / total_weight

        # To add "random spaces", we can simply respect the strict order but allow gaps.
        # Actually, "based on total commits sizes" means bigger commits might take "more time" (distance to next commit)?
        # Or bigger commits happen on days with fewer other commits?
        # The prompt says: "based on total commits sizes and average size per according to dates and times"
        # Interpreting this: Bigger commits should spaced out more?
        # Let's stick to: Gap after commit proportional to commit size.

        gap_share = weight / total_weight
        allocated_seconds = gap_share * total_duration_sec

        # We place the commit roughly at the end of its allocated block?
        # Or better: construct a timeline of "points" and map commits to points.

        # Better heuristic:
        # Map cumulative weight to time.
        # Target time = Start + (Cumulative Weight / Total Weight) * Total Duration
        # But this target time needs to be mapped to Valid Days/Hours.

        target_seconds_from_start = (current_cumulative_weight / total_weight) * total_duration_sec

        # Map seconds back to (Day, Time)
        day_idx = int(target_seconds_from_start // day_duration_sec)
        seconds_into_day = target_seconds_from_start % day_duration_sec

        # Clamp day_idx
        if day_idx >= len(valid_days):
            day_idx = len(valid_days) - 1
            seconds_into_day = day_duration_sec - 1  # End of last day

        target_day = valid_days[day_idx]

        # Add start_time offset
        start_seconds = sh * 3600 + sm * 60
        final_seconds_of_day = start_seconds + seconds_into_day

        # Add randomness: +/- some variation, but ensure order is kept?
        # Preserving strict order with randomness is tricky.
        # Simple approach: The calculated time is the "base".
        # We can add a small random jitter, but must ensure T(i) < T(i+1).
        # Since we just need to ensure T(i) >= T(i-1), we can track `last_assigned_time`.

        # Let's finalize the base time first.
        final_hour = int(final_seconds_of_day // 3600)
        final_minute = int((final_seconds_of_day % 3600) // 60)
        final_second = int(final_seconds_of_day % 60)

        dt = datetime.datetime.combine(
            target_day, datetime.time(final_hour, final_minute, final_second)
        )

        if hasattr(tz, "localize"):
            dt = tz.localize(dt)
        else:
            dt = dt.replace(tzinfo=tz)

        # Jitter?
        # Optional.

        schedule[commit["hash"]] = dt.isoformat()

        current_cumulative_weight += weight

    return schedule

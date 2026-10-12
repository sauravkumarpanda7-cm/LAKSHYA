def xp_for_next_level(level):
    """XP required to go from `level` to `level + 1`."""
    return 100 + (level - 1) * 50


def level_info(total_xp):
    """Return (level, xp_in_current_level, xp_needed_for_next)."""
    level = 1
    remaining = total_xp or 0
    while remaining >= xp_for_next_level(level):
        remaining -= xp_for_next_level(level)
        level += 1
    return level, remaining, xp_for_next_level(level)


def level_title(level):
    if level >= 20:
        return "Legend"
    if level >= 15:
        return "Master"
    if level >= 10:
        return "Expert"
    if level >= 5:
        return "Scholar"
    if level >= 2:
        return "Learner"
    return "Novice"
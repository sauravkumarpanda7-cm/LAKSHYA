from datetime import datetime

from app import db
from app.models import UserAchievement


# Each achievement: key, name, description, icon
ACHIEVEMENTS = [
    {"key": "first_quest", "name": "First Steps",  "desc": "Complete your first quest",       "icon": "🚀"},
    {"key": "tasks_10",    "name": "Task Master",  "desc": "Complete 10 quests",              "icon": "📚"},
    {"key": "tasks_50",    "name": "Unstoppable",  "desc": "Complete 50 quests",              "icon": "⚔️"},
    {"key": "level_2",     "name": "Rising Star",  "desc": "Reach Level 2",                   "icon": "⭐"},
    {"key": "level_5",     "name": "Scholar",      "desc": "Reach Level 5",                   "icon": "🎓"},
    {"key": "level_10",    "name": "Expert",       "desc": "Reach Level 10",                  "icon": "👑"},
    {"key": "streak_3",    "name": "On Fire",      "desc": "Maintain a 3-day streak",         "icon": "🔥"},
    {"key": "streak_7",    "name": "Week Warrior", "desc": "Maintain a 7-day streak",         "icon": "🌟"},
    {"key": "streak_30",   "name": "Consistency",  "desc": "Maintain a 30-day streak",        "icon": "💎"},
    {"key": "xp_100",      "name": "Century",      "desc": "Earn 100 XP",                     "icon": "💯"},
    {"key": "xp_500",      "name": "Half-K",       "desc": "Earn 500 XP",                     "icon": "⚡"},
    {"key": "xp_1000",     "name": "Millennium",   "desc": "Earn 1,000 XP",                   "icon": "🏅"},
]


ACHIEVEMENT_BY_KEY = {a["key"]: a for a in ACHIEVEMENTS}


def _conditions(user):
    done = sum(1 for t in user.tasks if t.completed)
    return {
        "first_quest": done >= 1,
        "tasks_10":    done >= 10,
        "tasks_50":    done >= 50,
        "level_2":     user.level >= 2,
        "level_5":     user.level >= 5,
        "level_10":    user.level >= 10,
        "streak_3":    user.streak >= 3,
        "streak_7":    user.streak >= 7,
        "streak_30":   user.streak >= 30,
        "xp_100":      user.xp >= 100,
        "xp_500":      user.xp >= 500,
        "xp_1000":     user.xp >= 1000,
    }


def check_and_award(user):
    """Check all achievements; award any new ones. Return list of newly unlocked (dicts)."""
    conditions = _conditions(user)
    already = {a.key for a in user.achievements}

    unlocked_keys = [k for k, ok in conditions.items() if ok and k not in already]

    for key in unlocked_keys:
        db.session.add(UserAchievement(user_id=user.id, key=key, unlocked_at=datetime.utcnow()))

    if unlocked_keys:
        db.session.commit()

    return [ACHIEVEMENT_BY_KEY[k] for k in unlocked_keys]


def user_achievements_for(user):
    """Return list of (achievement_dict, is_unlocked, unlocked_at)."""
    unlocked = {a.key: a.unlocked_at for a in user.achievements}
    out = []
    for a in ACHIEVEMENTS:
        out.append((a, a["key"] in unlocked, unlocked.get(a["key"])))
    return out
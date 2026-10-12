from datetime import date, datetime

from flask import (
    Blueprint, redirect, request, session, render_template, flash, url_for
)

from app import db
from app.models import Task, User
from app.utils.levels import level_info, level_title
from app.utils.achievements import (
    check_and_award, user_achievements_for, ACHIEVEMENTS
)

task_bp = Blueprint("task", __name__)


def current_user():
    """Return the logged-in user, or None."""
    user_id = session.get("user")
    return db.session.get(User, user_id) if user_id else None


@task_bp.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))

    # --- Daily reset: if it's a new day, uncheck all completed tasks ---
    today = date.today()
    did_reset = False

    if user.last_task_reset is None:
        user.last_task_reset = today
        db.session.commit()
    elif user.last_task_reset < today:
        Task.query.filter_by(user_id=user.id, completed=True).update({
            "completed": False,
            "completed_at": None,
        })
        user.last_task_reset = today
        db.session.commit()
        did_reset = True

    if did_reset:
        flash("🌅 New day! Your completed quests have been reset. Ready to go again?", "info")

    # --- Load tasks + achievements ---
    tasks = (
        Task.query
        .filter_by(user_id=user.id)
        .order_by(Task.completed, Task.id.desc())
        .all()
    )

    lvl, in_lvl, need = level_info(user.xp)
    ach_list = user_achievements_for(user)
    unlocked_count = sum(1 for _, u, _ in ach_list if u)

    return render_template(
        "dashboard.html",
        user=user,
        tasks=tasks,
        user_xp_in_level=in_lvl,
        user_xp_needed=need,
        user_title=level_title(lvl),
        achievements=ach_list,
        unlocked_count=unlocked_count,
        total_achievements=len(ACHIEVEMENTS),
    )


@task_bp.route("/add-task", methods=["POST"])
def add_task():
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))

    title = (request.form.get("title") or "").strip()
    if title:
        try:
            reward = int(request.form.get("xp_reward") or 50)
        except ValueError:
            reward = 50
        reward = max(10, min(reward, 200))

        db.session.add(Task(title=title[:200], user_id=user.id, xp_reward=reward))
        db.session.commit()
        flash(f"Quest added! (+{reward} XP)", "success")

    return redirect(url_for("task.dashboard"))


@task_bp.route("/complete/<int:id>", methods=["POST"])
def complete_task(id):
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))

    task = Task.query.filter_by(id=id, user_id=user.id).first()

    if task and not task.completed:
        task.completed = True
        task.completed_at = datetime.utcnow()

        old_level = user.level
        user.xp += task.xp_reward
        new_level, _, _ = level_info(user.xp)
        user.level = new_level

        db.session.commit()

        newly = check_and_award(user)
        for a in newly:
            flash(f"{a['icon']} Achievement unlocked — {a['name']}", "success")

        if user.level > old_level:
            flash(f"🎉 Level up! You reached Level {user.level}", "success")
        else:
            flash(f"+{task.xp_reward} XP earned!", "success")

    return redirect(url_for("task.dashboard"))


@task_bp.route("/delete/<int:id>", methods=["POST"])
def delete_task(id):
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))

    task = Task.query.filter_by(id=id, user_id=user.id).first()
    if task:
        db.session.delete(task)
        db.session.commit()
        flash("Quest removed.", "info")

    return redirect(url_for("task.dashboard"))
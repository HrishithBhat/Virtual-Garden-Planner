from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from database.connection import close_db, get_db_cursor
from backend.models import (
    GardenJournal,
    Notification,
    Schedule,
    ScheduleTask,
    User,
    AIMemory,
)


@dataclass
class AIInsight:
    message: str
    priority: str = "medium"
    metadata: Optional[Dict[str, Any]] = None


class AIOrchestrator:
    """Aggregate user gardening data into a structured context for AI prompts."""

    def __init__(self, user_id: int, username: Optional[str] = None) -> None:
        self.user_id = user_id
        self.username = username
        self._garden_cache: Optional[List[Dict[str, Any]]] = None
        self._context_cache: Optional[Dict[str, Any]] = None

    def build_context(self) -> Dict[str, Any]:
        if self._context_cache is not None:
            return self._context_cache

        # Ensure AI-driven rewards evaluation runs before building context
        try:
            from backend.models import Rewards
            Rewards.evaluate_pending(self.user_id)
        except Exception:
            pass

        profile = self._get_profile()
        garden = self._get_garden_state()
        schedules = self._get_schedule_state(garden.get("items", []))
        journals = self._get_journal_state()
        notifications = self._get_notifications()
        weed_sessions = self._get_recent_weed_sessions()
        chat_summary = self._summarize_general_chat()
        memory = self._get_memory()

        context: Dict[str, Any] = {
            "profile": profile,
            "garden": garden,
            "schedules": schedules,
            "journals": journals,
            "notifications": notifications,
            "weed_sessions": weed_sessions,
            "chat_summary": chat_summary,
            "memory": memory,
        }
        insights = self._derive_insights(context)
        context["insights"] = insights_to_dict(insights)
        context["generated_at"] = self._iso(datetime.utcnow())

        self._context_cache = context
        return context

    def build_prompt(self, history: Sequence[Dict[str, Any]], user_message: str) -> Tuple[str, Dict[str, Any]]:
        context = self.build_context()
        context_text = self.render_context(context)
        history_text = self._render_history(history)

        preface = (
            "You are a proactive gardening companion that understands the user's plants, schedules, "
            "and recent activities. Maintain a warm, encouraging tone at an 8th-grade reading level. "
            "ALWAYS reply using ONLY bullet points starting with '- '. Prefer concrete actions over theory.\n\n"
            "Output format (strict):\n"
            "- Quick answer: 1–2 bullets summarising the direct reply.\n"
            "- Best option / Good option / Excellent option: include relevant care choices, max one bullet each.\n"
            "- Steps: 3–7 action bullets explaining what to do.\n"
            "- Warnings: include only when risk exists.\n"
            "- Next actions: 2–4 bullets for immediate follow-up.\n"
            "Cap the total at 6–12 bullets. No tables. No code unless asked."
        )

        prompt_parts = [preface]
        if context_text:
            prompt_parts.append(f"Gardening context:\n{context_text}")
        if history_text:
            prompt_parts.append(f"Conversation so far:\n{history_text}")
        prompt_parts.append(f"User: {user_message}\nAssistant:")

        prompt = "\n\n".join(prompt_parts)
        return prompt, context

    def render_context(self, context: Dict[str, Any]) -> str:
        lines: List[str] = []
        profile = context.get("profile") or {}
        if profile:
            lines.append(
                f"User {profile.get('username') or self.username or 'gardener'} · role {profile.get('role') or 'user'} · "
                f"pro={'yes' if profile.get('is_pro') else 'no'}"
            )
            if profile.get("member_since"):
                lines.append(f"Member since {profile['member_since']}")

        garden = context.get("garden", {})
        items = garden.get("items") or []
        if items:
            lines.append("Garden plants:")
            for item in items[:5]:
                plant = item.get("plant_name") or "Unknown plant"
                nickname = item.get("nickname") or "no nickname"
                last_watered = item.get("last_watered") or "n/a"
                interval = item.get("watering_interval_days") or "?"
                lines.append(
                    f"- {plant} ({nickname}) · last watered {last_watered} · water every {interval} day(s)"
                )

        schedules = context.get("schedules") or {}
        schedule_items = schedules.get("items") or []
        if schedule_items:
            lines.append("Schedules:")
            for sched in schedule_items[:5]:
                plant = sched.get("plant_name") or "Plant"
                completed = sched.get("tasks_completed") or 0
                total = sched.get("tasks_total") or 0
                next_task = sched.get("next_task") or {}
                if next_task.get("task_text"):
                    lines.append(
                        f"- {plant}: Day {next_task.get('day')} → {next_task.get('task_text')} (done {completed}/{total})"
                    )
                else:
                    lines.append(f"- {plant}: schedule complete ({completed}/{total})")

        journal_state = context.get("journals") or {}
        journal_items = journal_state.get("items") or []
        if journal_items:
            lines.append("Journal highlights:")
            for journal in journal_items[:3]:
                latest = journal.get("latest_entry") or {}
                highlight = latest.get("notes") or "no recent entry"
                lines.append(
                    f"- {journal.get('title')}: {journal.get('entry_count', 0)} entries · last {journal.get('latest_entry_date') or 'n/a'} · {highlight}"
                )

        weeds = context.get("weed_sessions") or []
        if weeds:
            lines.append("Weed detections:")
            for entry in weeds[:3]:
                lines.append(
                    f"- {entry.get('name') or 'Unknown weed'} · confidence {entry.get('confidence_display')} · {entry.get('captured_at') or 'recent'}"
                )

        notifications = context.get("notifications") or []
        if notifications:
            lines.append("Alerts:")
            for notif in notifications[:3]:
                lines.append(f"- {notif.get('message')}")

        insights = context.get("insights") or []
        if insights:
            lines.append("Insights:")
            for insight in insights[:4]:
                message = (insight.get("message") if isinstance(insight, dict) else getattr(insight, "message", "")).strip()
                if message:
                    lines.append(f"- {message}")

        mem = context.get("memory") or {}
        prefs = mem.get("preference") or []
        if prefs:
            lines.append("Preferences:")
            for p in prefs[:3]:
                k = p.get("key") or "pref"
                v = p.get("value")
                try:
                    if isinstance(v, (dict, list)):
                        import json as _j
                        v = self._shorten(_j.dumps(v))
                except Exception:
                    pass
                lines.append(f"- {k}: {v}")

        chat_summary = context.get("chat_summary") or {}
        if chat_summary.get("total_messages"):
            lines.append(
                f"Chat history: {chat_summary['total_messages']} messages · last at {chat_summary.get('last_message_at') or 'n/a'}"
            )

        return "\n".join(lines)

    # --- Context builders -------------------------------------------------

    def _get_profile(self) -> Dict[str, Any]:
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                "SELECT id, username, role, is_pro, created_at FROM users WHERE id = %s LIMIT 1",
                (self.user_id,),
            )
            row = cur.fetchone() or {}
            return {
                "id": row.get("id"),
                "username": row.get("username") or self.username,
                "role": row.get("role") or "user",
                "is_pro": bool(row.get("is_pro")),
                "member_since": self._iso(row.get("created_at")),
            }
        except Exception:
            return {
                "id": self.user_id,
                "username": self.username,
                "role": "user",
                "is_pro": False,
                "member_since": None,
            }
        finally:
            close_db(conn, cur)

    def _get_garden_items(self) -> List[Dict[str, Any]]:
        if self._garden_cache is None:
            try:
                self._garden_cache = User.get_garden(self.user_id) or []
            except Exception:
                self._garden_cache = []
        return self._garden_cache

    def _get_garden_state(self) -> Dict[str, Any]:
        items = []
        for item in self._get_garden_items():
            plant = item.get("plant") or {}
            items.append(
                {
                    "garden_id": item.get("garden_id"),
                    "plant_id": item.get("plant_id"),
                    "plant_name": plant.get("name"),
                    "nickname": item.get("nickname"),
                    "planted_on": self._iso(item.get("planted_on")),
                    "last_watered": self._iso(item.get("last_watered")),
                    "watering_interval_days": item.get("watering_interval_days"),
                    "location": item.get("location"),
                    "schedule_id": item.get("schedule_id"),
                }
            )
        return {
            "items": items,
            "count": len(items),
        }

    def _get_schedule_state(self, garden_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        summaries: List[Dict[str, Any]] = []
        next_actions: List[Dict[str, Any]] = []
        for item in garden_items:
            schedule_id = item.get("schedule_id")
            if not schedule_id:
                continue
            schedule = Schedule.get_by_id(schedule_id)
            if not schedule:
                continue
            tasks = ScheduleTask.get_for_schedule(schedule_id) or []
            total = len(tasks)
            completed = sum(1 for t in tasks if bool(t.get("completed")))
            next_task = next((t for t in tasks if not bool(t.get("completed"))), None)
            summary = {
                "schedule_id": schedule_id,
                "garden_id": item.get("garden_id"),
                "plant_name": item.get("plant_name"),
                "tasks_total": total,
                "tasks_completed": completed,
                "next_task": {
                    "day": next_task.get("day") if next_task else None,
                    "task_index": next_task.get("task_index") if next_task else None,
                    "task_text": self._shorten(next_task.get("task_text")) if next_task else None,
                },
                "tasks": [
                    {
                        "day": task.get("day"),
                        "task_index": task.get("task_index"),
                        "task_text": task.get("task_text"),
                        "completed": bool(task.get("completed")),
                        "completed_at": self._iso(task.get("completed_at")),
                    }
                    for task in tasks
                ],
            }
            summaries.append(summary)
            if next_task and next_task.get("task_text"):
                next_actions.append(
                    {
                        "type": "schedule_task",
                        "title": f"{item.get('plant_name') or 'Plant'} – Day {next_task.get('day')}",
                        "body": self._shorten(next_task.get("task_text"), 240),
                        "schedule_id": schedule_id,
                        "garden_id": item.get("garden_id"),
                    }
                )
        return {"items": summaries, "next_actions": next_actions}

    def _get_journal_state(self) -> Dict[str, Any]:
        journals = []
        try:
            journal_models = GardenJournal.list_for_user(self.user_id) or []
        except Exception:
            journal_models = []
        if not journal_models:
            return {"items": []}

        conn, cur = get_db_cursor()
        try:
            for journal in journal_models:
                cur.execute(
                    """
                    SELECT entry_date, notes
                    FROM garden_journal_entries
                    WHERE journal_id = %s
                    ORDER BY entry_date DESC, created_at DESC
                    LIMIT 1
                    """,
                    (journal.id,),
                )
                row = cur.fetchone()
                latest_entry = None
                if row:
                    latest_entry = {
                        "entry_date": self._iso(row.get("entry_date")),
                        "notes": self._shorten(row.get("notes")),
                    }
                journals.append(
                    {
                        "journal_id": journal.id,
                        "title": journal.title,
                        "plant_name": journal.plant_name,
                        "entry_count": journal.entry_count,
                        "latest_entry_date": self._iso(journal.latest_entry_date),
                        "latest_entry": latest_entry,
                    }
                )
        finally:
            close_db(conn, cur)
        return {"items": journals}

    def _get_notifications(self) -> List[Dict[str, Any]]:
        try:
            rows = Notification.get_for_user(self.user_id, limit=5) or []
        except Exception:
            rows = []
        notifications: List[Dict[str, Any]] = []
        for row in rows:
            notifications.append(
                {
                    "id": row.get("id"),
                    "message": row.get("message"),
                    "url": row.get("url"),
                    "created_at": self._iso(row.get("created_at")),
                }
            )
        return notifications

    def _get_recent_weed_sessions(self) -> List[Dict[str, Any]]:
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                """
                SELECT id, result_name, result_json, updated_at
                FROM weed_sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC, id DESC
                LIMIT 5
                """,
                (self.user_id,),
            )
            rows = cur.fetchall() or []
        except Exception:
            rows = []
        finally:
            close_db(conn, cur)

        sessions: List[Dict[str, Any]] = []
        for row in rows:
            result_data: Dict[str, Any] = {}
            try:
                if row.get("result_json"):
                    result_data = json.loads(row["result_json"])
            except Exception:
                result_data = {}
            confidence = result_data.get("confidence") or row.get("confidence")
            sessions.append(
                {
                    "session_id": row.get("id"),
                    "name": result_data.get("name") or row.get("result_name"),
                    "type": result_data.get("type"),
                    "harmful_effects": result_data.get("harmful_effects") or [],
                    "control_methods": result_data.get("control_methods") or [],
                    "confidence": confidence,
                    "confidence_display": self._format_confidence(confidence),
                    "captured_at": self._iso(row.get("updated_at")),
                }
            )
        return sessions

    def _get_memory(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        try:
            prefs = AIMemory.list_for_user(self.user_id, 'preference')
            if prefs:
                out['preference'] = prefs
        except Exception:
            pass
        try:
            care = AIMemory.list_for_user(self.user_id, 'care_event')
            if care:
                out['care_event'] = care
        except Exception:
            pass
        return out

    def _summarize_general_chat(self) -> Dict[str, Any]:
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                "SELECT COUNT(*) AS total, MAX(created_at) AS last_at FROM general_chats WHERE user_id = %s",
                (self.user_id,),
            )
            aggregate = cur.fetchone() or {}
            cur.execute(
                "SELECT message FROM general_chats WHERE user_id = %s ORDER BY id DESC LIMIT 3",
                (self.user_id,),
            )
            previews = cur.fetchall() or []
        except Exception:
            aggregate = {}
            previews = []
        finally:
            close_db(conn, cur)

        return {
            "total_messages": int(aggregate.get("total") or 0),
            "last_message_at": self._iso(aggregate.get("last_at")),
            "last_messages_preview": [
                self._shorten(row.get("message"))
                for row in reversed(previews)
                if row and row.get("message")
            ],
        }

    # --- Insights ---------------------------------------------------------

    def _derive_insights(self, context: Dict[str, Any]) -> List[AIInsight]:
        insights: List[AIInsight] = []
        for action in context.get("schedules", {}).get("next_actions", []):
            message = f"Upcoming task for {action.get('title')}: {action.get('body')}"
            insights.append(AIInsight(message=message, priority="high", metadata=action))
        for notif in context.get("notifications", []):
            insights.append(AIInsight(message=notif.get("message", ""), priority="medium", metadata=notif))
        weeds = context.get("weed_sessions", [])
        if weeds:
            latest = weeds[0]
            if latest.get("name"):
                message = f"Recent weed detected: {latest['name']} (confidence {latest.get('confidence_display')})."
            else:
                message = "Weed detection available for review."
            insights.append(AIInsight(message=message, priority="info", metadata=latest))
        return insights

    # --- Helpers ----------------------------------------------------------

    def _render_history(self, history: Sequence[Dict[str, Any]]) -> str:
        if not history:
            return ""
        lines: List[str] = []
        for msg in history:
            role = (msg.get("role") or "user").strip().lower()
            content = self._shorten(msg.get("message"))
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _shorten(text: Optional[str], limit: int = 180) -> str:
        if not text:
            return ""
        compact = " ".join(str(text).split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

    @staticmethod
    def _iso(value: Optional[Any]) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()).isoformat()
        if value in (None, ""):
            return None
        return str(value)

    @staticmethod
    def _format_confidence(confidence: Optional[Any]) -> str:
        try:
            if confidence is None:
                return "?"
            val = float(confidence)
            if val > 1:
                return f"{val:.0f}%"
            return f"{val * 100:.0f}%"
        except Exception:
            return "?"


def insights_to_dict(insights: Iterable[AIInsight]) -> List[Dict[str, Any]]:
    return [asdict(insight) for insight in insights]

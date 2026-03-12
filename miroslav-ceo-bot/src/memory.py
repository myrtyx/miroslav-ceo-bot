import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PROFILES_DIR = Path("data/profiles")


class ProfileManager:
    def __init__(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, telegram_id: int) -> Path:
        return PROFILES_DIR / f"{telegram_id}.json"

    def get(self, telegram_id: int) -> dict | None:
        path = self._path(telegram_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load profile %s: %s", telegram_id, e)
            return None

    def save(self, profile: dict):
        tid = profile["telegram_id"]
        path = self._path(tid)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

    def get_or_create_intern(self, telegram_id: int, username: str, display_name: str) -> dict:
        profile = self.get(telegram_id)
        if profile:
            profile["last_seen"] = datetime.now(timezone.utc).isoformat()
            profile["interaction_count"] = profile.get("interaction_count", 0) + 1
            self.save(profile)
            return profile
        profile = {
            "telegram_id": telegram_id,
            "telegram_username": username or "",
            "display_name": display_name or username or "Unknown",
            "role": {
                "title": "Стажёр (Intern)",
                "department": "Пока не определён",
            },
            "backstory": "",
            "personal_facts": [],
            "inside_jokes": [],
            "topics_discussed": [],
            "fake_kpi": {},
            "interaction_count": 1,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save(profile)
        logger.info("Created intern profile for %s (%s)", display_name, telegram_id)
        return profile

    def assign_role(self, username: str, title: str, department: str) -> dict | None:
        profile = self._find_by_username(username)
        if not profile:
            profile = {
                "telegram_id": 0,
                "telegram_username": username,
                "display_name": username,
                "role": {"title": title, "department": department},
                "backstory": "",
                "personal_facts": [],
                "inside_jokes": [],
                "topics_discussed": [],
                "fake_kpi": {},
                "interaction_count": 0,
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            profile["role"] = {"title": title, "department": department}
        self.save(profile)
        return profile

    def set_backstory(self, username: str, backstory: str) -> bool:
        profile = self._find_by_username(username)
        if not profile:
            return False
        profile["backstory"] = backstory
        self.save(profile)
        return True

    def update_telegram_id(self, username: str, telegram_id: int, display_name: str):
        profile = self._find_by_username(username)
        if profile and profile["telegram_id"] == 0:
            old_path = self._path(0)
            profile["telegram_id"] = telegram_id
            profile["display_name"] = display_name
            self.save(profile)
            if old_path.exists() and telegram_id != 0:
                old_path.unlink(missing_ok=True)

    def get_all(self) -> list[dict]:
        profiles = []
        for path in PROFILES_DIR.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profiles.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue
        return profiles

    def apply_batch_update(self, updates: dict):
        for tid_str, changes in updates.items():
            try:
                tid = int(tid_str)
            except ValueError:
                continue
            profile = self.get(tid)
            if not profile:
                continue
            for field in ("personal_facts", "inside_jokes", "topics_discussed"):
                add_key = f"{field}_add"
                if add_key in changes:
                    existing = set(profile.get(field, []))
                    for item in changes[add_key]:
                        if item not in existing:
                            profile.setdefault(field, []).append(item)
            if "fake_kpi" in changes:
                profile["fake_kpi"] = changes["fake_kpi"]
            self.save(profile)

    def get_least_known(self) -> dict | None:
        profiles = self.get_all()
        if not profiles:
            return None
        def info_score(p):
            return (len(p.get("personal_facts", []))
                    + len(p.get("inside_jokes", []))
                    + len(p.get("topics_discussed", []))
                    + (1 if p.get("backstory") else 0))
        return min(profiles, key=info_score)

    def _find_by_username(self, username: str) -> dict | None:
        username = username.lstrip("@").lower()
        for profile in self.get_all():
            if profile.get("telegram_username", "").lower() == username:
                return profile
        return None

    def format_profile(self, profile: dict) -> str:
        role = profile.get("role", {})
        lines = [
            f"@{profile.get('telegram_username', '???')} ({profile.get('display_name', '???')})",
            f"Должность: {role.get('title', '—')}",
            f"Отдел: {role.get('department', '—')}",
        ]
        if profile.get("backstory"):
            lines.append(f"Backstory: {profile['backstory']}")
        if profile.get("personal_facts"):
            lines.append(f"Факты: {', '.join(profile['personal_facts'])}")
        if profile.get("inside_jokes"):
            lines.append(f"Шутки: {', '.join(profile['inside_jokes'])}")
        if profile.get("topics_discussed"):
            lines.append(f"Темы: {', '.join(profile['topics_discussed'])}")
        if profile.get("fake_kpi"):
            kpi = profile["fake_kpi"]
            kpi_str = ", ".join(f"{k}: {v}" for k, v in kpi.items())
            lines.append(f"KPI: {kpi_str}")
        lines.append(f"Взаимодействий: {profile.get('interaction_count', 0)}")
        return "\n".join(lines)

    def format_team(self) -> str:
        profiles = self.get_all()
        if not profiles:
            return "Команда пуста. Используй /assign для добавления сотрудников."
        departments: dict[str, list] = {}
        for p in profiles:
            dept = p.get("role", {}).get("department", "Без отдела")
            departments.setdefault(dept, []).append(p)
        lines = ["ORGCHART — LakeChain Inc.", ""]
        for dept, members in sorted(departments.items()):
            lines.append(f"[{dept}]")
            for m in members:
                title = m.get("role", {}).get("title", "—")
                name = m.get("display_name", m.get("telegram_username", "???"))
                username = m.get("telegram_username", "")
                lines.append(f"  @{username} ({name}) — {title}")
            lines.append("")
        return "\n".join(lines)

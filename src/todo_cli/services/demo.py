"""Demo mode for Todo CLI — generates realistic fake tasks for testing."""

import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from ..domain import Todo, TodoStatus, Priority
from ..storage import Storage
from ..config import get_config

# Tag all demo tasks so they can be identified and removed
DEMO_TAG = "_demo"

# ---------------------------------------------------------------------------
# Task templates: (text, project, priority, tags, contexts, description,
#                  assignees, pinned, effort)
# ---------------------------------------------------------------------------

_TASK_TEMPLATES = [
    # ---- Work ----
    ("Review Q1 marketing report", "work", Priority.HIGH,
     ["review", "marketing"], ["office"],
     "Go through the 28-page report and leave comments before Friday stand-up.",
     ["sarah"], False, "2h"),
    ("Prepare sprint retrospective slides", "work", Priority.MEDIUM,
     ["meeting", "agile"], ["office"],
     "Summarize velocity, blockers, and action items from Sprint 14.",
     [], False, "1h"),
    ("Update onboarding documentation", "work", Priority.LOW,
     ["docs"], ["office"],
     "New hire complained several screenshots are outdated.",
     ["james"], False, "4h"),
    ("Submit expense report for March", "work", Priority.HIGH,
     ["finance"], ["office"], "", [], False, "30m"),
    ("Draft proposal for client rebrand", "work", Priority.CRITICAL,
     ["proposal", "design"], ["office"],
     "Client expects first draft by end of week.",
     ["mike", "lisa"], True, "8h"),
    ("Fix broken CI pipeline", "work", Priority.CRITICAL,
     ["bug", "devops"], ["office"],
     "Main branch builds have been red since yesterday evening.",
     ["alex"], True, ""),
    ("Schedule one-on-ones with direct reports", "work", Priority.MEDIUM,
     ["meeting", "management"], ["office"], "", [], False, "30m"),
    ("Write unit tests for payment module", "work", Priority.HIGH,
     ["testing", "backend"], ["office"],
     "Coverage is at 42% — target is 80%.",
     [], False, "4h"),
    ("Review pull request #247", "work", Priority.MEDIUM,
     ["review", "code"], ["office"], "", ["carlos"], False, "1h"),
    ("Migrate database to PostgreSQL 16", "work", Priority.HIGH,
     ["database", "migration"], ["office"],
     "Test locally first, then stage. Coordinate with DBA team.",
     ["anna", "dave"], False, "2d"),
    ("Create Q2 OKRs", "work", Priority.MEDIUM,
     ["planning", "management"], ["office"], "", [], False, "2h"),
    ("Respond to customer escalation ticket #1892", "work", Priority.CRITICAL,
     ["support", "urgent"], ["office"],
     "Enterprise customer reporting data loss — top priority.",
     [], True, ""),
    ("Set up staging environment for new microservice", "work", Priority.MEDIUM,
     ["devops", "infrastructure"], ["office"], "", ["alex"], False, "4h"),
    ("Refactor authentication middleware", "work", Priority.MEDIUM,
     ["refactor", "backend", "security"], ["office"],
     "Current implementation doesn't handle token refresh properly.",
     [], False, "6h"),
    ("Prepare board presentation", "work", Priority.HIGH,
     ["presentation", "management"], ["office"], "", [], False, "3h"),

    # ---- Personal ----
    ("Buy groceries for dinner party", "personal", Priority.MEDIUM,
     ["shopping", "cooking"], ["errands"],
     "Need: salmon, asparagus, lemons, wine, dessert.",
     [], False, "1h"),
    ("Call mom for her birthday", "personal", Priority.HIGH,
     ["family"], ["phone"], "", [], False, "30m"),
    ("Renew car registration", "personal", Priority.HIGH,
     ["car", "admin"], ["errands"],
     "Expires end of month. Need emissions test first.",
     [], False, "2h"),
    ("Research vacation destinations for August", "personal", Priority.LOW,
     ["travel", "planning"], ["computer"],
     "Looking at Portugal, Croatia, or Japan.",
     [], False, ""),
    ("Return library books", "personal", Priority.LOW,
     ["errands"], ["errands"], "Due by Thursday.", [], False, "30m"),
    ("Plan surprise anniversary dinner", "personal", Priority.MEDIUM,
     ["planning", "family"], ["phone"],
     "Book that Italian place downtown. Check if they do private rooms.",
     [], False, "1h"),
    ("Organize photo albums from 2025", "personal", Priority.LOW,
     ["photos", "organization"], ["computer"], "", [], False, "3h"),
    ("Pick up dry cleaning", "personal", Priority.LOW,
     ["errands"], ["errands"], "", [], False, "30m"),
    ("Write thank-you notes for wedding gifts", "personal", Priority.MEDIUM,
     ["social"], ["home"], "", [], False, "2h"),
    ("Cancel unused streaming subscriptions", "personal", Priority.LOW,
     ["finance", "subscriptions"], ["computer"],
     "Check Hulu, Paramount+, and that meditation app.",
     [], False, "30m"),

    # ---- Home ----
    ("Fix leaky kitchen faucet", "home", Priority.HIGH,
     ["plumbing", "repair"], ["home"],
     "Dripping constantly — probably needs a new washer.",
     [], False, "1h"),
    ("Repaint guest bedroom", "home", Priority.LOW,
     ["painting", "renovation"], ["home"],
     "Picked out 'Coastal Fog' from Benjamin Moore.",
     [], False, "1d"),
    ("Clean out garage", "home", Priority.MEDIUM,
     ["organization", "declutter"], ["home"],
     "Donate old bikes, recycle electronics, organize tools.",
     [], False, "4h"),
    ("Replace HVAC filter", "home", Priority.MEDIUM,
     ["maintenance"], ["home"], "Buy MERV-13 20x25x1 filter.", [], False, "30m"),
    ("Set up smart thermostat", "home", Priority.LOW,
     ["smart_home", "tech"], ["home"],
     "Ecobee arrived yesterday. Need to wire it up.",
     [], False, "2h"),
    ("Mow the lawn", "home", Priority.MEDIUM,
     ["yard", "maintenance"], ["home"], "", [], False, "1h"),
    ("Organize pantry", "home", Priority.LOW,
     ["organization", "kitchen"], ["home"],
     "Get clear containers for dry goods.",
     [], False, "2h"),
    ("Schedule roof inspection", "home", Priority.HIGH,
     ["maintenance", "repair"], ["phone"],
     "Noticed a few missing shingles after last storm.",
     [], True, ""),

    # ---- Side Project ----
    ("Fix login page CSS bug", "side-project", Priority.HIGH,
     ["bug", "frontend", "css"], ["computer"],
     "Button overlaps on mobile viewport below 375px.",
     [], False, "1h"),
    ("Add dark mode toggle", "side-project", Priority.MEDIUM,
     ["feature", "frontend", "ui"], ["computer"],
     "Use CSS custom properties for easy theme switching.",
     [], False, "3h"),
    ("Write README for open source release", "side-project", Priority.MEDIUM,
     ["docs", "open_source"], ["computer"],
     "Include installation, usage examples, and contributing guide.",
     [], False, "2h"),
    ("Implement rate limiting on API", "side-project", Priority.HIGH,
     ["feature", "backend", "security"], ["computer"],
     "Use sliding window algorithm. 100 req/min per API key.",
     [], False, "4h"),
    ("Set up GitHub Actions CI/CD", "side-project", Priority.MEDIUM,
     ["devops", "ci"], ["computer"],
     "Run tests, lint, and deploy to staging on merge to main.",
     [], False, "2h"),
    ("Design landing page mockup", "side-project", Priority.LOW,
     ["design", "marketing"], ["computer"], "", [], False, "3h"),
    ("Benchmark database queries", "side-project", Priority.MEDIUM,
     ["performance", "database"], ["computer"],
     "The user search endpoint is taking 800ms — should be under 100ms.",
     [], False, "2h"),
    ("Add email notification system", "side-project", Priority.LOW,
     ["feature", "backend", "email"], ["computer"],
     "Use SendGrid. Start with welcome email and password reset.",
     [], False, "6h"),

    # ---- Health ----
    ("Schedule dentist appointment", "health", Priority.MEDIUM,
     ["dental", "appointment"], ["phone"],
     "Last checkup was 8 months ago.", [], False, ""),
    ("Run 5K three times this week", "health", Priority.MEDIUM,
     ["running", "cardio"], ["home"],
     "Training for the charity 10K in June.",
     [], False, ""),
    ("Meal prep for the week", "health", Priority.MEDIUM,
     ["nutrition", "cooking"], ["home"],
     "Focus on high-protein, low-carb meals.",
     [], False, "3h"),
    ("Book annual physical exam", "health", Priority.HIGH,
     ["medical", "appointment"], ["phone"],
     "Need to get blood work done beforehand.",
     [], True, ""),
    ("Try the new yoga studio downtown", "health", Priority.LOW,
     ["yoga", "fitness"], ["errands"],
     "They have a free intro class on Saturday mornings.",
     [], False, "1h"),
    ("Refill prescriptions", "health", Priority.HIGH,
     ["medical", "pharmacy"], ["errands"],
     "Running low on allergy meds.", [], False, "30m"),
    ("Start meditation habit", "health", Priority.LOW,
     ["wellness", "mindfulness"], ["home"],
     "Try 10 minutes every morning using Headspace.",
     [], False, ""),
    ("Get new running shoes", "health", Priority.MEDIUM,
     ["shopping", "running"], ["errands"],
     "Current pair has 500+ miles. Try Brooks Ghost 16.",
     [], False, "1h"),
]


def _random_due_date(rng: random.Random) -> Optional[datetime]:
    """Generate a random due date: some past (overdue), some today, some future, some None."""
    choice = rng.random()
    now = datetime.now(tz=timezone.utc)
    if choice < 0.15:
        # Overdue (1–14 days ago)
        return now - timedelta(days=rng.randint(1, 14))
    elif choice < 0.30:
        # Due today
        return now.replace(hour=23, minute=59, second=0, microsecond=0)
    elif choice < 0.75:
        # Upcoming (1–30 days)
        return now + timedelta(days=rng.randint(1, 30))
    else:
        # No due date
        return None


def _random_status(rng: random.Random) -> TodoStatus:
    """Mostly pending, some in-progress, a few completed."""
    r = rng.random()
    if r < 0.50:
        return TodoStatus.PENDING
    elif r < 0.75:
        return TodoStatus.IN_PROGRESS
    elif r < 0.90:
        return TodoStatus.COMPLETED
    elif r < 0.95:
        return TodoStatus.BLOCKED
    else:
        return TodoStatus.CANCELLED


class DemoDataGenerator:
    """Generates realistic fake tasks for demo/testing purposes."""

    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage or Storage(get_config())

    def generate_tasks(self, count: int = 30, seed: Optional[int] = None) -> List[Todo]:
        """Generate a set of realistic demo tasks across multiple projects."""
        rng = random.Random(seed)

        templates = list(_TASK_TEMPLATES)
        rng.shuffle(templates)

        # If more tasks requested than templates, cycle through templates
        tasks: List[Todo] = []
        for i in range(count):
            tmpl = templates[i % len(templates)]
            (text, project, priority, tags, contexts, description,
             assignees, pinned, effort) = tmpl

            status = _random_status(rng)
            due_date = _random_due_date(rng)

            # Every demo task gets the DEMO_TAG
            task_tags = list(tags) + [DEMO_TAG]

            todo = Todo(
                id=0,  # Will be assigned by storage
                text=text,
                project=project,
                priority=priority,
                tags=task_tags,
                context=list(contexts),
                description=description,
                assignees=list(assignees),
                pinned=pinned,
                effort=effort,
                due_date=due_date,
                status=status,
                completed=(status == TodoStatus.COMPLETED),
            )
            tasks.append(todo)

        return tasks

    def populate(self, count: int = 30, seed: Optional[int] = None) -> int:
        """Generate and save demo tasks. Returns number created."""
        tasks = self.generate_tasks(count, seed)
        for task in tasks:
            self.storage.add_todo(task)
        return len(tasks)

    def clear(self) -> int:
        """Remove all demo tasks (identified by DEMO_TAG). Returns count removed."""
        removed = 0
        projects = self.storage.list_projects() or []
        for project in projects:
            proj_obj, todos = self.storage.load_project(project)
            demo_ids = [t.id for t in todos if DEMO_TAG in (t.tags or [])]
            if not demo_ids:
                continue
            remaining = [t for t in todos if t.id not in set(demo_ids)]
            if proj_obj is not None:
                self.storage.save_project(proj_obj, remaining)
            removed += len(demo_ids)
        return removed

    def has_demo_data(self) -> bool:
        """Check if demo data exists."""
        return self.get_demo_count() > 0

    def get_demo_count(self) -> int:
        """Count existing demo tasks."""
        count = 0
        for todo in self.storage.get_all_todos():
            if DEMO_TAG in (todo.tags or []):
                count += 1
        return count

"""Enhanced natural language parser for Todo CLI."""

import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import parsedatetime
from fuzzywuzzy import fuzz, process

from .todo import Todo, Priority, TodoStatus
from .config import ConfigModel
from .utils.datetime import now_utc, ensure_aware


@dataclass
class ParsedTask:
    """Represents a parsed task with extracted metadata."""
    text: str
    project: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    context: List[str] = field(default_factory=list)
    priority: Optional[Priority] = None
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    scheduled_date: Optional[datetime] = None
    assignees: List[str] = field(default_factory=list)
    stakeholders: List[str] = field(default_factory=list)
    effort: Optional[str] = None
    recurrence: Optional[str] = None
    pinned: bool = False
    location: Optional[str] = None
    waiting_for: List[str] = field(default_factory=list)
    energy_level: Optional[str] = None
    time_estimate: Optional[int] = None
    url: Optional[str] = None


@dataclass
class ParseError:
    """Represents a parsing error with suggestions."""
    message: str
    position: Optional[int] = None
    suggestions: List[str] = field(default_factory=list)
    severity: str = "error"  # error, warning, info


class SmartDateParser:
    """Intelligent date parser using natural language."""
    
    def __init__(self):
        self.cal = parsedatetime.Calendar()
        # Common relative date patterns (all timezone-aware)
        self.patterns = {
            'today': lambda: ensure_aware(now_utc().replace(hour=23, minute=59, second=59)),
            'tomorrow': lambda: ensure_aware((now_utc() + timedelta(days=1)).replace(hour=23, minute=59, second=59)),
            'yesterday': lambda: ensure_aware((now_utc() - timedelta(days=1)).replace(hour=23, minute=59, second=59)),
            'next week': lambda: ensure_aware(now_utc() + timedelta(weeks=1)),
            'next month': lambda: ensure_aware(self._add_months(now_utc(), 1)),
            'end of week': lambda: ensure_aware(self._end_of_week()),
            'end of month': lambda: ensure_aware(self._end_of_month()),
        }
    
    def _add_months(self, date: datetime, months: int) -> datetime:
        """Add months to a date."""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        return date.replace(year=year, month=month)
    
    def _end_of_week(self) -> datetime:
        """Get end of current week (Sunday)."""
        now = now_utc()
        days_until_sunday = 6 - now.weekday()
        return now + timedelta(days=days_until_sunday)
    
    def _end_of_month(self) -> datetime:
        """Get end of current month."""
        now = now_utc()
        next_month = self._add_months(now, 1)
        return next_month.replace(day=1) - timedelta(days=1)
    
    def parse(self, date_str: str) -> Optional[datetime]:
        """Parse natural language date string."""
        if not date_str:
            return None
        
        date_str = date_str.lower().strip()
        
        # Check common patterns first
        if date_str in self.patterns:
            return self.patterns[date_str]()
        
        # Try parsedatetime
        time_struct, parse_status = self.cal.parse(date_str)
        if parse_status > 0:
            parsed_dt = datetime(*time_struct[:6])
            return ensure_aware(parsed_dt)
        
        # Try regex patterns for specific formats
        patterns = [
            (r'^(\d{4}-\d{2}-\d{2})$', '%Y-%m-%d'),
            (r'^(\d{2}/\d{2}/\d{4})$', '%m/%d/%Y'),
            (r'^(\d{1,2}/\d{1,2})$', '%m/%d'),  # Assumes current year
        ]
        
        for pattern, fmt in patterns:
            match = re.match(pattern, date_str)
            if match:
                try:
                    if '%Y' not in fmt:
                        # Add current year
                        date_str_with_year = f"{date_str}/{now_utc().year}"
                        parsed_dt = datetime.strptime(date_str_with_year, f"{fmt}/%Y")
                        return ensure_aware(parsed_dt)
                    parsed_dt = datetime.strptime(date_str, fmt)
                    return ensure_aware(parsed_dt)
                except ValueError:
                    continue
        
        return None


class NaturalLanguageParser:
    """Enhanced natural language parser for task creation."""
    
    def __init__(self, config: ConfigModel):
        self.config = config
        self.date_parser = SmartDateParser()
        
        # Metadata extraction patterns
        self.patterns = {
            'project': re.compile(r'#([a-zA-Z0-9_-]+)'),
            'tags': re.compile(r'@([a-zA-Z0-9_-]+)'),
            'priority': re.compile(r'~([a-zA-Z0-9_-]+)'),  # Match any word, validate later
            'effort': re.compile(r'\*([a-zA-Z0-9_-]+)'),
            'assignees': re.compile(r'\+([a-zA-Z0-9_-]+)'),
            'stakeholders': re.compile(r'&([a-zA-Z0-9_-]+)'),
            'recurrence': re.compile(r'%([a-zA-Z0-9_:-]+)'),
            'pinned': re.compile(r'\[PINNED\]|\[PIN\]|\[P\]'),
            'url': re.compile(r'https?://[^\s]+'),
            'waiting': re.compile(r'\(waiting:?\s*([^)]+)\)'),
        }
        
        # Date extraction patterns
        self.date_patterns = {
            'due': re.compile(r'(?:due|!)\s*([^@#~*+&%\[\(]+?)(?=\s*[@#~*+&%\[\(]|$)', re.IGNORECASE),
            'start': re.compile(r'(?:start|starts?)\s*([^@#~*+&%\[\(]+?)(?=\s*[@#~*+&%\[\(]|$)', re.IGNORECASE),
            # Add word boundaries around 'at' to avoid matching inside words like 'latest'
            'scheduled': re.compile(r'(?:scheduled?|\bat\b)\s*([^@#~*+&%\[\(]+?)(?=\s*[@#~*+&%\[\(]|$)', re.IGNORECASE),
        }
        
        # Energy level patterns
        self.energy_patterns = re.compile(r'(?:energy|focus):\s*(high|medium|low)', re.IGNORECASE)
        
        # Time estimate patterns
        self.time_patterns = re.compile(r'(?:estimate|est):\s*(\d+(?:h|m|hr|min|hours?|minutes?))', re.IGNORECASE)
    
    def parse(self, input_text: str, project_hint: Optional[str] = None) -> Tuple[ParsedTask, List[ParseError]]:
        """Parse natural language input into structured task data."""
        try:
            errors = []
            parsed = ParsedTask(text="")
            
            if not input_text.strip():
                errors.append(ParseError("Empty task text", suggestions=["Add a task description"]))
                return parsed, errors
            
            # Start with the full input
            original_text = input_text
            remaining_text = input_text.strip()
            
            # Extract project
            project_match = self.patterns['project'].search(remaining_text)
            if project_match:
                parsed.project = project_match.group(1)
                remaining_text = remaining_text.replace(project_match.group(0), '', 1)
            elif project_hint:
                parsed.project = project_hint
            
            # Extract tags (context-aware)
            for match in self.patterns['tags'].finditer(remaining_text):
                tag = match.group(1)
                # Determine if it's a context or regular tag
                if tag in ['home', 'work', 'office', 'phone', 'computer', 'errands', 'online']:
                    parsed.context.append(tag)
                else:
                    parsed.tags.append(tag)
            
            # Remove processed tags
            remaining_text = self.patterns['tags'].sub('', remaining_text)
            
            # Extract priority
            priority_match = self.patterns['priority'].search(remaining_text)
            if priority_match:
                priority_val = priority_match.group(1).lower()
                try:
                    parsed.priority = Priority(priority_val)
                    remaining_text = remaining_text.replace(priority_match.group(0), '', 1)
                except ValueError:
                    errors.append(ParseError(
                        f"Invalid priority: {priority_match.group(1)}",
                        suggestions=["Use: critical, high, medium, low"]
                    ))
            
            # Extract effort
            effort_match = self.patterns['effort'].search(remaining_text)
            if effort_match:
                parsed.effort = effort_match.group(1)
                remaining_text = remaining_text.replace(effort_match.group(0), '', 1)
            
            # Extract assignees
            for match in self.patterns['assignees'].finditer(remaining_text):
                parsed.assignees.append(match.group(1))
            remaining_text = self.patterns['assignees'].sub('', remaining_text)
            
            # Extract stakeholders
            for match in self.patterns['stakeholders'].finditer(remaining_text):
                parsed.stakeholders.append(match.group(1))
            remaining_text = self.patterns['stakeholders'].sub('', remaining_text)
            
            # Extract recurrence
            recurrence_match = self.patterns['recurrence'].search(remaining_text)
            if recurrence_match:
                parsed.recurrence = recurrence_match.group(1)
                remaining_text = remaining_text.replace(recurrence_match.group(0), '', 1)
            
            # Check for pinned
            if self.patterns['pinned'].search(remaining_text):
                parsed.pinned = True
                remaining_text = self.patterns['pinned'].sub('', remaining_text)
            
            # Extract URL
            url_match = self.patterns['url'].search(remaining_text)
            if url_match:
                parsed.url = url_match.group(0)
                remaining_text = remaining_text.replace(url_match.group(0), '', 1)
            
            # Extract waiting for
            waiting_match = self.patterns['waiting'].search(remaining_text)
            if waiting_match:
                waiting_items = [item.strip() for item in waiting_match.group(1).split(',')]
                parsed.waiting_for.extend(waiting_items)
                remaining_text = remaining_text.replace(waiting_match.group(0), '', 1)
            
            # Extract energy level
            energy_match = self.energy_patterns.search(remaining_text)
            if energy_match:
                parsed.energy_level = energy_match.group(1).lower()
                remaining_text = remaining_text.replace(energy_match.group(0), '', 1)
            
            # Extract time estimate
            time_match = self.time_patterns.search(remaining_text)
            if time_match:
                time_str = time_match.group(1)
                parsed.time_estimate = self._parse_time_estimate(time_str)
                remaining_text = remaining_text.replace(time_match.group(0), '', 1)
            
            # Extract dates
            parsed.due_date, remaining_text = self._extract_date(remaining_text, 'due')
            parsed.start_date, remaining_text = self._extract_date(remaining_text, 'start')
            parsed.scheduled_date, remaining_text = self._extract_date(remaining_text, 'scheduled')

            # Freeform due date fallback (e.g., "for tomorrow", "by Monday", "on 9/21")
            if not parsed.due_date:
                remaining_text, freeform_due = self._extract_freeform_due(remaining_text)
                if freeform_due:
                    parsed.due_date = freeform_due
            
            # Clean up remaining text for task description
            parsed.text = ' '.join(remaining_text.split()).strip()
            
            # Only raise a description error if the original input was metadata-only
            if not parsed.text:
                # Heuristic: original contained only metadata tokens and/or dates
                if self._looks_metadata_only(original_text):
                    errors.append(ParseError(
                        "No task description found after parsing metadata",
                        suggestions=["Ensure task has descriptive text along with metadata"]
                    ))
                else:
                    # Fall back to the original text if our parsing consumed everything unexpectedly
                    parsed.text = original_text.strip()
            
            return parsed, errors
            
        except Exception as e:
            # Return error instead of crashing
            return ParsedTask(text=input_text), [ParseError(f"Parsing failed: {str(e)}")]
    
    def _extract_date(self, text: str, date_type: str) -> Tuple[Optional[datetime], str]:
        """Extract and parse date from text."""
        pattern = self.date_patterns.get(date_type)
        if not pattern:
            return None, text
        
        match = pattern.search(text)
        if match:
            date_str = match.group(1).strip()
            parsed_date = self.date_parser.parse(date_str)
            if parsed_date:
                # Remove the matched date from text
                new_text = text.replace(match.group(0), '', 1)
                new_text = self._clean_trailing_preposition(new_text)
                return parsed_date, new_text
        
        return None, text
    
    def _parse_time_estimate(self, time_str: str) -> Optional[int]:
        """Parse time estimate string to minutes."""
        time_str = time_str.lower()
        
        # Extract number
        num_match = re.search(r'(\d+)', time_str)
        if not num_match:
            return None
        
        num = int(num_match.group(1))
        
        # Determine unit
        if any(unit in time_str for unit in ['h', 'hr', 'hour']):
            return num * 60  # Convert hours to minutes
        elif any(unit in time_str for unit in ['m', 'min', 'minute']):
            return num
        else:
            # Default to minutes if no unit specified
            return num

    def _clean_trailing_preposition(self, text: str) -> str:
        """Remove dangling prepositions left after stripping date phrases."""
        # Remove trailing 'for', 'by', 'on', or 'at' if they end the string
        cleaned = re.sub(r"\s*\b(?:for|by|on|at)\b\s*$", "", text, flags=re.IGNORECASE)
        # Normalize whitespace
        return ' '.join(cleaned.split()).strip()

    def _extract_freeform_due(self, text: str) -> Tuple[str, Optional[datetime]]:
        """Extract a freeform due date from text (e.g., 'for tomorrow', 'by Monday', 'on 9/21').
        Returns updated_text, parsed_date. Only removes substring when parse is successful.
        """
        if not text:
            return text, None
        
        working = text
        
        # 1) Look for known relative keywords first (e.g., tomorrow, today, next week)
        keywords = sorted(self.date_parser.patterns.keys(), key=len, reverse=True)
        if keywords:
            kw_pattern = re.compile(r"\\b(" + "|".join(re.escape(k) for k in keywords) + r")\\b", re.IGNORECASE)
            m = kw_pattern.search(working)
            if m:
                phrase = m.group(0)
                dt = self.date_parser.parse(phrase)
                if dt:
                    new_text = (working[:m.start()] + working[m.end():])
                    new_text = self._clean_trailing_preposition(new_text)
                    return new_text, dt
        
        # 2) Common preposition + date phrase (validated by SmartDateParser)
        prepositional = re.compile(r"\b(?:for|by|on|at)\b\s+([^@#~*+&%\[\(]+?)(?=\s*[@#~*+&%\[\(]|$)", re.IGNORECASE)
        m2 = prepositional.search(working)
        if m2:
            phrase = m2.group(1).strip()
            dt = self.date_parser.parse(phrase)
            if dt:
                # Remove the entire matched segment (including the preposition)
                new_text = working.replace(m2.group(0), '', 1)
                new_text = self._clean_trailing_preposition(new_text)
                return new_text, dt
        
        return text, None

    def _looks_metadata_only(self, original_text: str) -> bool:
        """Heuristic to detect if the input contained only metadata tokens without real description."""
        s = original_text.strip()
        if not s:
            return True
        # Remove known metadata tokens and see if anything meaningful remains
        s = self.patterns['project'].sub('', s)
        s = self.patterns['tags'].sub('', s)
        s = self.patterns['priority'].sub('', s)
        s = self.patterns['effort'].sub('', s)
        s = self.patterns['assignees'].sub('', s)
        s = self.patterns['stakeholders'].sub('', s)
        s = self.patterns['recurrence'].sub('', s)
        s = self.patterns['pinned'].sub('', s)
        s = self.patterns['url'].sub('', s)
        s = self.patterns['waiting'].sub('', s)
        s = self.energy_patterns.sub('', s)
        s = self.time_patterns.sub('', s)
        # Also strip explicit date directives
        for key in ['due', 'start', 'scheduled']:
            patt = self.date_patterns.get(key)
            if patt:
                s = patt.sub('', s)
        # Normalize whitespace
        s = ' '.join(s.split()).strip()
        return len(s) == 0
    
    def suggest_corrections(self, input_text: str, available_projects: List[str] = None,
                          available_tags: List[str] = None,
                          available_people: List[str] = None) -> List[str]:
        """Provide suggestions for improving the input."""
        suggestions = []
        
        if available_projects:
            # Check for project typos
            project_matches = self.patterns['project'].findall(input_text)
            for project in project_matches:
                if project not in available_projects:
                    close_matches = process.extractBests(project, available_projects, 
                                                       scorer=fuzz.ratio, score_cutoff=70, limit=3)
                    if close_matches:
                        matches = [match[0] for match in close_matches]
                        suggestions.append(f"Did you mean project #{matches[0]} instead of #{project}?")
        
        if available_tags:
            # Check for tag typos
            tag_matches = self.patterns['tags'].findall(input_text)
            for tag in tag_matches:
                if tag not in available_tags and tag not in ['home', 'work', 'office', 'phone', 'computer']:
                    close_matches = process.extractBests(tag, available_tags,
                                                       scorer=fuzz.ratio, score_cutoff=70, limit=2)
                    if close_matches:
                        matches = [match[0] for match in close_matches]
                        suggestions.append(f"Did you mean @{matches[0]} instead of @{tag}?")
        
        if available_people:
            # Check for people typos
            assignee_matches = self.patterns['assignees'].findall(input_text)
            for assignee in assignee_matches:
                if assignee not in available_people:
                    close_matches = process.extractBests(assignee, available_people,
                                                       scorer=fuzz.ratio, score_cutoff=70, limit=2)
                    if close_matches:
                        matches = [match[0] for match in close_matches]
                        suggestions.append(f"Did you mean +{matches[0]} instead of +{assignee}?")
        
        return suggestions


class TaskBuilder:
    """Builds Todo objects from parsed task data."""
    
    def __init__(self, config: ConfigModel):
        self.config = config
    
    def build(self, parsed: ParsedTask, todo_id: int = 1) -> Todo:
        """Build a Todo object from parsed task data."""
        return Todo(
            id=todo_id,
            text=parsed.text,
            project=parsed.project or self.config.default_project,
            tags=parsed.tags,
            context=parsed.context,
            priority=parsed.priority or Priority(self.config.default_priority.value if isinstance(self.config.default_priority, Priority) else self.config.default_priority),
            due_date=parsed.due_date,
            start_date=parsed.start_date,
            scheduled_date=parsed.scheduled_date,
            assignees=parsed.assignees,
            stakeholders=parsed.stakeholders,
            effort=parsed.effort or "",
            recurrence=parsed.recurrence,
            pinned=parsed.pinned,
            location=parsed.location,
            waiting_for=parsed.waiting_for,
            energy_level=parsed.energy_level or "medium",
            time_estimate=parsed.time_estimate,
            url=parsed.url,
        )


def parse_task_input(input_text: str, config: ConfigModel, 
                    project_hint: Optional[str] = None,
                    available_projects: List[str] = None,
                    available_tags: List[str] = None,
                    available_people: List[str] = None) -> Tuple[ParsedTask, List[ParseError], List[str]]:
    """Main function to parse task input with suggestions."""
    parser = NaturalLanguageParser(config)
    parsed, errors = parser.parse(input_text, project_hint)
    suggestions = parser.suggest_corrections(input_text, available_projects, available_tags, available_people)
    
    return parsed, errors, suggestions

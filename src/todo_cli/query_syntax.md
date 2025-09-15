# Query Engine Syntax Specification

## Overview

The Enhanced Query Engine provides a powerful, intuitive syntax for searching and filtering todos with complex criteria.

## Basic Syntax

### Simple Text Search
```bash
todo search "fix bug"           # Search in task text
todo search text:"database"     # Explicit text field search
```

### Field-Specific Queries
```bash
todo search priority:high                    # Tasks with high priority
todo search project:webapp                   # Tasks in webapp project  
todo search status:pending                   # Tasks with pending status
todo search assignee:john                    # Tasks assigned to john
todo search tag:urgent                       # Tasks with urgent tag
todo search due:today                        # Tasks due today
todo search created:this-week                # Tasks created this week
```

## Date Queries

### Absolute Dates
```bash
todo search due:2023-12-25                   # Specific date
todo search due:2023-12                      # Entire month
todo search created:2023                     # Entire year
```

### Relative Dates  
```bash
todo search due:today                        # Due today
todo search due:tomorrow                     # Due tomorrow
todo search due:this-week                    # Due this week
todo search due:next-month                   # Due next month
todo search created:last-7-days              # Created in last 7 days
```

### Date Ranges
```bash
todo search due:2023-12-01..2023-12-31      # Date range
todo search due:today..next-week             # Mixed range
todo search created:>2023-12-01              # After date
todo search due:<tomorrow                    # Before date
```

## Logical Operators

### AND (default)
```bash
todo search priority:high status:pending     # AND is implicit
todo search priority:high AND status:pending # Explicit AND
```

### OR
```bash
todo search priority:high OR priority:critical
todo search tag:urgent OR tag:important
todo search (project:webapp OR project:api) status:pending
```

### NOT
```bash
todo search NOT status:completed             # Exclude completed
todo search priority:high NOT assignee:john  # High priority, not assigned to john
todo search -status:completed                # Short syntax for NOT
```

### Parentheses for Grouping
```bash
todo search (priority:high OR priority:critical) AND status:pending
todo search project:webapp AND (tag:bug OR tag:security)
```

## Advanced Field Queries

### Multiple Values
```bash
todo search priority:high,critical           # Priority is high OR critical
todo search tag:urgent,important             # Has urgent OR important tag
todo search assignee:john,sarah              # Assigned to john OR sarah
```

### Wildcards and Patterns
```bash
todo search text:"fix*"                      # Text starts with "fix"
todo search text:"*bug*"                     # Text contains "bug"
todo search project:web*                     # Project starts with "web"
todo search tag:@*                           # Any context tag
```

### Numeric Comparisons
```bash
todo search estimate:>2h                     # More than 2 hours
todo search estimate:<30m                    # Less than 30 minutes
todo search estimate:1h..4h                  # Between 1-4 hours
todo search id:>100                          # ID greater than 100
```

### Existence Checks
```bash
todo search has:due-date                     # Has a due date
todo search has:assignee                     # Has an assignee
todo search has:estimate                     # Has time estimate
todo search missing:due-date                 # Missing due date
todo search empty:assignee                   # No assignee
```

## Special Queries

### Status-Based
```bash
todo search is:overdue                       # Overdue tasks
todo search is:completed                     # Completed tasks  
todo search is:pinned                        # Pinned tasks
todo search is:blocked                       # Blocked tasks
todo search is:active                        # Active (not completed/cancelled)
```

### Time-Based
```bash
todo search is:today                         # Due today
todo search is:this-week                     # Due this week
todo search is:overdue                       # Past due date
todo search is:upcoming                      # Has future due date
```

### Effort and Energy
```bash
todo search effort:large                     # Large effort tasks
todo search energy:low                       # Low energy tasks
todo search effort:quick,small               # Quick or small effort
```

## Sorting Integration

### Sort with Query
```bash
todo search priority:high sort:due-date      # High priority, sorted by due date
todo search project:webapp sort:priority,created  # Multi-field sort
todo search tag:urgent sort:-priority        # Descending priority
```

## Saved Queries and Shortcuts

### Save Queries
```bash
todo search priority:high status:pending --save="high-priority-pending"
todo search is:overdue assignee:me --save="my-overdue"
```

### Use Saved Queries
```bash
todo search @high-priority-pending           # Use saved query
todo search @my-overdue                      # Another saved query
```

## Query Examples

### Real-World Scenarios
```bash
# Find all urgent work tasks assigned to me that are overdue
todo search tag:urgent project:work assignee:me is:overdue

# Find all high/critical priority tasks due this week
todo search priority:high,critical due:this-week

# Find all tasks waiting for someone else
todo search has:waiting-for NOT status:completed

# Find all quick tasks I can do when energy is low  
todo search effort:quick,small energy:low assignee:me is:active

# Find all project-related tasks without due dates
todo search has:project missing:due-date

# Find tasks created recently that might need attention
todo search created:last-7-days NOT status:completed sort:priority
```

## Implementation Notes

### Query Parser
- Lexical analysis to tokenize the query string
- Recursive descent parser for complex expressions
- AST (Abstract Syntax Tree) generation
- Query optimization and validation

### Execution Engine  
- Field-specific filtering functions
- Date parsing and comparison utilities
- Text search with fuzzy matching
- Efficient multi-criteria filtering

### Performance Considerations
- Index frequently queried fields
- Cache compiled queries
- Lazy evaluation for large datasets
- Streaming results for memory efficiency
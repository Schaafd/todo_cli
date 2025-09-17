# Todo CLI Analytics System - Complete Guide

## 📊 Overview

The Todo CLI Analytics system provides comprehensive insights into your productivity patterns, task management effectiveness, and project progress. This advanced analytics engine helps you understand your work habits, identify bottlenecks, and optimize your workflow.

## 🚀 Getting Started

### Quick Start

```bash
# Generate a weekly productivity overview
todo analytics overview --timeframe weekly

# View time tracking analytics with heatmap
todo analytics time --period week --heatmap

# Analyze specific project
todo analytics projects --project "MyProject"

# Export analytics data
todo analytics export all --format json
```

## 🏗️ Core Components

### 1. Productivity Analytics

**Purpose**: Analyzes your task completion patterns, productivity trends, and work effectiveness.

**Key Metrics**:
- Completion rate percentage
- Average daily task completion
- Productivity score (0-100)
- Focus score (0-100)
- Task patterns and trends

**CLI Usage**:
```bash
# Basic productivity analysis
todo analytics overview

# Weekly analysis with JSON export
todo analytics overview --timeframe weekly --format json --export weekly_report.json

# Custom timeframe analysis
todo analytics overview --timeframe monthly --format csv
```

**Example Output**:
```
============================================================
               📊 PRODUCTIVITY ANALYTICS OVERVIEW               
============================================================

📈 KEY METRICS
Metric                Value
------------------  -------
Completion Rate     75.5%
Avg Daily Tasks     3.2
Productivity Score  82.1/100
Focus Score         68.9/100

💡 KEY INSIGHTS
📈 completion_rate: Your completion rate is trending upward
📉 overdue_tasks: You have 3 overdue tasks that need attention
➡️ time_management: Your peak hours are between 9-11 AM
```

### 2. Time Tracking & Analytics

**Purpose**: Tracks time spent on tasks and provides detailed productivity insights.

**Features**:
- Automatic time tracking
- Manual time entry
- Productivity heatmaps
- Work pattern analysis
- Estimation accuracy tracking

**CLI Usage**:
```bash
# Weekly time analysis
todo analytics time --period week

# Show productivity heatmap
todo analytics time --period month --heatmap

# Filter by project
todo analytics time --project "Work" --period week

# Filter by tag
todo analytics time --tag "urgent" --period today
```

**Time Tracking Commands**:
```bash
# Start tracking time for a task
todo track start <task-id>

# Stop current tracking
todo track stop

# Add manual time entry
todo track add <task-id> --duration 2h --description "Code review"

# View active tracking
todo track status
```

**Heatmap Example**:
```
🔥 PRODUCTIVITY HEATMAP
       0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23
Mon:                           .  :  #  █  █  #  :  .        .  :  #  .
Tue:                           .  :  #  █  #  :  .           .  :  :  .
Wed:                              :  #  █  █  #  :  .           .  .
Thu:                           .  :  #  █  █  :  .              .  :  .
Fri:                              :  #  #  :  .                 .
Sat:                                 .  :  .
Sun:                                 .  .

Legend: █ = High activity, # = Medium, : = Low, . = Minimal, (space) = No activity
```

### 3. Project Analytics

**Purpose**: Provides project-level insights including health scores, burndown charts, and forecasting.

**Key Features**:
- Project health scoring
- Burndown chart generation
- Velocity tracking
- Completion forecasting
- Resource allocation analysis

**CLI Usage**:
```bash
# Overview of all projects
todo analytics projects

# Analyze specific project
todo analytics projects --project "Website Redesign"

# Show all project details
todo analytics projects --all
```

**Project Health Indicators**:
- ✅ **Healthy**: 80-100% health score
- ⚠️ **Warning**: 60-79% health score  
- 🚨 **Critical**: Below 60% health score

**Example Output**:
```
📁 PROJECT: Website Redesign

✅ Health Score: 85.2/100 (Healthy)
   • Completion Rate: 78.5%
   • Velocity Score: 89.0/100
   • Quality Score: 88.0/100

Metric           Value
-------------  -------
Total Tasks         45
Completed          35
In Progress         7
Overdue            3

🔮 Project Forecast:
   • Estimated Completion: 2024-02-15
   • Confidence Level: 87.3%
   • Days Remaining: 12
```

### 4. Custom Dashboards

**Purpose**: Create personalized dashboards with custom widgets and metrics.

**CLI Usage**:
```bash
# List available dashboards
todo analytics dashboard --list

# View specific dashboard
todo analytics dashboard --name "My Dashboard"

# Create new dashboard interactively
todo analytics dashboard --name "Project Overview" --create
```

**Dashboard Creation Example**:
```bash
$ todo analytics dashboard --name "Daily Overview" --create
Creating dashboard: Daily Overview
Available data sources: todo_metrics, project_metrics, time_tracking

Widget name (or 'done' to finish): Completion Rate
Data source for Completion Rate: todo_metrics
Widget type: metric

Widget name (or 'done' to finish): Time Today
Data source for Time Today: time_tracking
Widget type: metric

Widget name (or 'done' to finish): done
Dashboard 'Daily Overview' created successfully!
```

### 5. Plugin System

**Purpose**: Extend analytics capabilities with custom plugins and integrations.

**Available Plugin Types**:
- **Analytics**: Custom metrics and insights
- **Dashboard**: Custom widgets and data sources
- **Integration**: Third-party service connections
- **Workflow**: Automation and triggers
- **Export**: Custom export formats
- **Notification**: Alert systems

**Plugin Management**:
```bash
# List all plugins
todo analytics plugins list

# Install plugin from directory
todo analytics plugins install /path/to/plugin

# Enable plugin
todo analytics plugins enable plugin_id

# Disable plugin
todo analytics plugins disable plugin_id

# List by type
todo analytics plugins list --type analytics

# Filter by status
todo analytics plugins list --status enabled
```

## 📋 Best Practices

### 1. Daily Workflow

**Morning Routine**:
```bash
# Check yesterday's productivity
todo analytics overview --timeframe daily

# Review time tracking
todo analytics time --period yesterday

# Start tracking first task
todo track start <task-id>
```

**Evening Review**:
```bash
# Stop time tracking
todo track stop

# Review daily productivity
todo analytics time --period today --heatmap

# Export daily report
todo analytics export analytics --timeframe daily --format json
```

### 2. Weekly Planning

**Monday Planning**:
```bash
# Review last week's performance
todo analytics overview --timeframe weekly

# Check project health
todo analytics projects

# Plan week based on insights
```

**Friday Review**:
```bash
# Generate weekly report
todo analytics overview --timeframe weekly --export weekly_report.json

# Review time allocation
todo analytics time --period week

# Export for external analysis
todo analytics export all --timeframe weekly --format csv
```

### 3. Project Management

**Project Setup**:
```bash
# Create project-specific dashboard
todo analytics dashboard --name "Project Alpha" --create

# Set up time tracking for project
todo track start <task-id> --project "Project Alpha"
```

**Regular Reviews**:
```bash
# Weekly project health check
todo analytics projects --project "Project Alpha"

# Monthly project analysis
todo analytics projects --project "Project Alpha" --all
```

### 4. Time Management Optimization

**Identify Peak Hours**:
```bash
# Monthly heatmap analysis
todo analytics time --period month --heatmap

# Export for deeper analysis
todo analytics export time --timeframe monthly --format csv
```

**Improve Estimation**:
- Track estimated vs actual time
- Review estimation accuracy reports
- Adjust estimates based on historical data

**Example Estimation Workflow**:
```bash
# Create task with estimate
todo add "Implement feature X" --estimate 4h

# Track actual time
todo track start <task-id>
todo track stop

# Review accuracy
todo analytics time --period week
```

## 📈 Advanced Analytics

### 1. Statistical Analysis

The analytics engine includes advanced statistical features:

- **Trend Analysis**: Identifies improving/declining patterns
- **Correlation Analysis**: Finds relationships between metrics
- **Regression Analysis**: Predicts future performance
- **Distribution Analysis**: Analyzes task completion patterns

### 2. Machine Learning Insights

**Pattern Recognition**:
- Work rhythm identification
- Productivity cycle detection
- Task difficulty estimation
- Optimal scheduling suggestions

**Predictive Analytics**:
- Project completion forecasting
- Resource requirement prediction
- Bottleneck identification
- Performance trend projection

### 3. Custom Metrics

**Creating Custom Analytics**:

```python
# Example custom plugin
from todo_cli.plugins import AnalyticsPlugin

class CustomProductivityPlugin(AnalyticsPlugin):
    def analyze(self, todos):
        # Custom analysis logic
        return {
            'custom_metric': calculate_custom_score(todos),
            'insights': generate_custom_insights(todos)
        }
```

## 🔧 Configuration

### Analytics Settings

Create `~/.config/todo-cli/analytics.yaml`:

```yaml
analytics:
  enabled: true
  default_timeframe: "weekly"
  auto_export: true
  export_format: "json"
  export_directory: "~/todo-reports"
  
time_tracking:
  auto_start: false
  remind_stop: true
  minimum_duration: 60  # seconds
  
dashboards:
  default_dashboard: "overview"
  auto_refresh: true
  refresh_interval: 300  # seconds
  
plugins:
  auto_load: true
  allowed_types: ["analytics", "dashboard", "export"]
```

### Performance Settings

```yaml
performance:
  cache_enabled: true
  cache_duration: 3600  # seconds
  max_history_days: 365
  parallel_processing: true
  max_workers: 4
```

## 🎯 Use Cases & Examples

### 1. Freelancer Productivity Tracking

**Setup**:
```bash
# Create client-specific projects
todo add "Client A - Website" --project "ClientA"
todo add "Client B - App Development" --project "ClientB"

# Start time tracking
todo track start <task-id> --project "ClientA"
```

**Analysis**:
```bash
# Weekly client breakdown
todo analytics time --period week

# Monthly project comparison
todo analytics projects --all

# Export for invoicing
todo analytics export time --format csv --output client_hours.csv
```

### 2. Software Development Team

**Daily Standups**:
```bash
# Team productivity overview
todo analytics overview --timeframe daily

# Sprint progress
todo analytics projects --project "Sprint 23"

# Burndown analysis
todo analytics projects --project "Sprint 23" --all
```

### 3. Student Academic Tracking

**Study Sessions**:
```bash
# Subject-specific tracking
todo add "Study Mathematics" --tag "math" --estimate 2h
todo track start <task-id>

# Weekly study analysis
todo analytics time --tag "math" --period week

# Productivity heatmap for optimal study times
todo analytics time --period month --heatmap
```

### 4. Personal Productivity Optimization

**Habit Formation**:
```bash
# Track daily habits
todo add "Morning Exercise" --tag "habit" --recurring daily

# Analyze consistency
todo analytics overview --timeframe monthly

# Identify patterns
todo analytics time --tag "habit" --period month --heatmap
```

## 🔍 Troubleshooting

### Common Issues

**1. Missing Analytics Data**
```bash
# Check data directory
todo config get data_dir

# Verify analytics enabled
todo config get analytics.enabled

# Rebuild analytics cache
todo analytics --rebuild-cache
```

**2. Performance Issues**
```bash
# Clear analytics cache
todo analytics --clear-cache

# Reduce history window
todo config set analytics.max_history_days 90

# Enable parallel processing
todo config set performance.parallel_processing true
```

**3. Plugin Issues**
```bash
# List plugin status
todo analytics plugins list

# Check plugin logs
todo analytics plugins logs <plugin-id>

# Reinstall plugin
todo analytics plugins uninstall <plugin-id>
todo analytics plugins install /path/to/plugin
```

### Debug Mode

Enable detailed logging:
```bash
# Temporary debug mode
TODO_DEBUG=true todo analytics overview

# Persistent debug mode
todo config set debug true
```

## 🔄 Data Export & Integration

### Export Formats

**JSON Export**:
```bash
todo analytics export all --format json --output report.json
```

**CSV Export**:
```bash
todo analytics export analytics --format csv --output productivity.csv
```

**Excel Export** (requires openpyxl):
```bash
todo analytics export all --format excel --output dashboard.xlsx
```

### Integration Examples

**Power BI Integration**:
1. Export data as CSV
2. Import into Power BI
3. Create custom visualizations

**Google Sheets Integration**:
1. Export as CSV
2. Import to Google Sheets
3. Use Google Apps Script for automation

**Custom API Integration**:
```python
import json
import requests

# Load exported data
with open('analytics_export.json', 'r') as f:
    data = json.load(f)

# Send to custom API
response = requests.post('https://api.mycompany.com/analytics', json=data)
```

## 📚 API Reference

### Analytics Engine API

```python
from todo_cli.analytics import ProductivityAnalyzer, AnalyticsTimeframe

# Initialize analyzer
analyzer = ProductivityAnalyzer()

# Generate report
report = analyzer.analyze_productivity(todos, AnalyticsTimeframe.WEEKLY)

# Access metrics
print(f"Completion Rate: {report.completion_rate}%")
print(f"Productivity Score: {report.productivity_score}/100")
```

### Plugin Development API

```python
from todo_cli.plugins import AnalyticsPlugin, PluginInfo, PluginType

class MyAnalyticsPlugin(AnalyticsPlugin):
    def get_info(self):
        return PluginInfo(
            id="my_plugin",
            name="My Analytics Plugin",
            version="1.0.0",
            author="Your Name",
            description="Custom analytics plugin",
            plugin_type=PluginType.ANALYTICS
        )
    
    def initialize(self):
        self.api.log("info", "Plugin initialized")
        return True
    
    def analyze(self, todos):
        # Your analysis logic
        return {"custom_metric": 42}
```

## 🛠️ Development & Contributing

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/your-repo/todo-cli
cd todo-cli

# Install development dependencies
uv sync --dev

# Run tests
uv run pytest tests/test_analytics.py -v

# Run analytics tests specifically
uv run pytest tests/test_analytics.py::TestProductivityAnalyzer -v
```

### Creating Custom Plugins

1. **Plugin Structure**:
```
my_plugin/
├── plugin.json          # Plugin manifest
├── main.py             # Plugin entry point
├── __init__.py
└── README.md
```

2. **Plugin Manifest** (`plugin.json`):
```json
{
  "id": "my_analytics_plugin",
  "name": "My Analytics Plugin",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Custom analytics functionality",
  "type": "analytics",
  "entry_point": "main.py",
  "min_cli_version": "1.0.0",
  "dependencies": [],
  "config_schema": {
    "api_key": {
      "type": "string",
      "required": true,
      "description": "API key for external service"
    }
  }
}
```

3. **Plugin Implementation** (`main.py`):
```python
from todo_cli.plugins import AnalyticsPlugin

class MyAnalyticsPlugin(AnalyticsPlugin):
    def initialize(self):
        self.api.log("info", "My plugin initialized")
        return True
    
    def cleanup(self):
        self.api.log("info", "My plugin cleaned up")
    
    def analyze(self, todos):
        # Your custom analysis
        return {"my_metric": len(todos)}
    
    def get_metrics(self, todos):
        return {"task_count": float(len(todos))}
```

### Running Tests

```bash
# Full test suite
uv run pytest tests/test_analytics.py

# Specific test class
uv run pytest tests/test_analytics.py::TestProductivityAnalyzer

# With coverage
uv run pytest tests/test_analytics.py --cov=todo_cli.analytics

# Performance tests
uv run pytest tests/test_analytics.py::TestEdgeCases::test_large_dataset_performance
```

## 📖 FAQ

**Q: How accurate are the productivity scores?**
A: Productivity scores are calculated using multiple factors including completion rates, time estimates vs actual time, task priorities, and trends. They provide relative insights rather than absolute measures.

**Q: Can I customize the analytics timeframes?**
A: Yes, you can use daily, weekly, monthly, yearly, or "all" timeframes. Custom date ranges can be implemented via plugins.

**Q: How is privacy handled with analytics data?**
A: All analytics data is stored locally by default. Export and sharing are explicit user actions. Plugins may have different privacy policies.

**Q: Can I analyze tasks from different projects together?**
A: Yes, the overview command analyzes all tasks, while project-specific commands focus on individual projects. You can filter by tags for cross-project analysis.

**Q: How do I backup my analytics data?**
A: Use the export functionality to create backups: `todo analytics export all --format json --output backup.json`

**Q: What's the performance impact of analytics?**
A: Analytics calculations are optimized and cached. For large datasets (>10,000 tasks), consider enabling parallel processing and adjusting cache settings.

## 🎉 Next Steps

1. **Start Simple**: Begin with basic overview and time tracking
2. **Establish Routine**: Incorporate analytics into daily/weekly workflows  
3. **Customize Gradually**: Add dashboards and plugins as needed
4. **Export Regularly**: Back up data and integrate with other tools
5. **Share Insights**: Use analytics to improve team productivity

For more advanced features and latest updates, check the [project repository](https://github.com/your-repo/todo-cli) and [plugin marketplace](https://todo-cli-plugins.com).

---

*This guide covers Todo CLI Analytics v5.0. For earlier versions, see the [version compatibility guide](./version_compatibility.md).*
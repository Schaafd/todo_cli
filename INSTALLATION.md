# Installation Guide

## Installing the Productivity Ninja CLI

### Prerequisites
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Global Installation

To install the CLI as a global command that you can use from anywhere:

```bash
# Clone the repository
git clone <your-repo-url>
cd todo_cli

# Install globally using uv
uv tool install --editable .
```

This will install the `todo` command globally and make it available from any directory.

### Verification

Test that the installation worked:

```bash
# From any directory
todo --help
todo list
todo dashboard
```

### Shell Completion (Optional)

For an enhanced experience with tab completion:

```bash
# One-time setup
source completion_setup.sh

# Or add to your shell profile for permanent setup
echo 'eval "$(_TODO_COMPLETE=zsh_source todo)"' >> ~/.zshrc  # For Zsh
echo 'eval "$(_TODO_COMPLETE=bash_source todo)"' >> ~/.bashrc  # For Bash
```

## Development Installation

If you want to contribute to the project:

```bash
# Install in development mode
uv pip install -e .

# Or run without installing
uv run todo --help
```

## Usage Examples

### Quick Start
```bash
# Add tasks with natural language
todo add "Review architecture proposal @meetings due friday"
todo add "Call doctor @phone ~high"
todo add "Deploy app #project1 +john due tomorrow"

# View organized task lists
todo list                    # All tasks organized by date
todo list --priority-sort    # Sort by priority within each view
todo list --pinned          # Show only pinned tasks

# Complete tasks
todo done 1

# Pin important tasks
todo pin 3

# View dashboard
todo dashboard

# See all projects
todo projects
```

### Advanced Features

#### Natural Language Parsing
The CLI supports rich natural language parsing:

- **Priority**: `~critical`, `~high`, `~medium`, `~low`
- **Tags**: `@meetings`, `@phone`, `@work`
- **Projects**: `#project1`, `#personal`
- **Due dates**: `due friday`, `due tomorrow`, `due 2023-12-25`
- **Assignees**: `+john`, `+sarah`
- **Stakeholders**: `&manager`, `&cto`
- **Pinning**: `[PIN]` or `[PINNED]`
- **Time estimates**: `est:2h`, `est:30m`
- **Energy levels**: `energy:high`, `energy:low`
- **Effort levels**: `*quick`, `*medium`, `*involved`

#### Task Organization
Tasks are automatically organized into views:

- **📅 Today**: Tasks due today
- **🕰 Tomorrow**: Tasks due tomorrow  
- **📆 Upcoming**: Tasks with future due dates
- **📋 Backlog**: Tasks without due dates

## Configuration

The CLI stores configuration and data in `~/.todo/`:
- `config.yaml` - User configuration
- `projects/` - Project-specific todo lists in Markdown format

## Uninstallation

To remove the globally installed CLI:

```bash
uv tool uninstall todo-cli
```
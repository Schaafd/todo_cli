# Changelog

All notable changes to the Todo CLI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2025-09-20

### 🚀 Major Improvements

#### App Sync Setup Reliability
- **Fixed critical setup hang issue** that could cause `todo app-sync setup` to freeze indefinitely
- **Added robust timeout handling** with configurable timeout values (default 60s, customizable via `--timeout`)
- **Improved interactive/non-interactive mode detection** - automatically detects terminal environments
- **Enhanced error handling** with graceful KeyboardInterrupt handling and clear error messages

#### Configuration System Overhaul  
- **Resolved YAML enum serialization issues** - enums now properly serialize to/from strings instead of Python objects
- **Fixed "No providers configured" bug** - AppSyncManager now correctly loads configured providers on initialization
- **Added backward compatibility** for existing configuration files with automatic migration
- **Improved configuration validation** with better error reporting

#### Enhanced Diagnostics and Troubleshooting
- **New `app-sync doctor` command** - comprehensive diagnostic tool for troubleshooting sync issues
  - Validates environment, configuration, credentials, and network connectivity
  - Provides actionable remediation suggestions
  - Checks both environment variables and keyring storage for tokens
- **Enhanced debug logging** throughout the app-sync system
- **Improved error messages** with specific guidance for common issues

### 🛠️ New Features

#### Command Line Interface
- **New setup options:**
  - `--skip-mapping` - Skip interactive project mapping for faster setup
  - `--timeout N` - Set custom timeout for network operations (default: 60 seconds)
  - `--no-interactive` - Force non-interactive mode (also auto-detected)
  - `--debug` - Enable detailed debug logging for troubleshooting

#### Environment Variable Support  
- **Full support for `TODOIST_API_TOKEN`** environment variable
- **Automatic fallback chain:** environment variable → command line flag → interactive prompt → keyring storage
- **Non-interactive automation** - perfect for CI/CD and scripted environments

### 🔧 Technical Improvements

#### Testing Infrastructure
- **Added comprehensive test suite** with 16 new tests covering:
  - App-sync models and enum functionality
  - Environment detection (interactive vs non-interactive)
  - Configuration directory and file handling
  - CLI command availability and import verification
  - Doctor command diagnostic components
- **Configured pytest** with proper settings, coverage reporting, and CI integration
- **Added GitHub Actions workflow** for automated testing on multiple Python versions
- **Test dependencies:** pytest-cov, pytest-mock, responses, respx for comprehensive mocking

#### Code Quality
- **Enhanced type safety** throughout the app-sync codebase
- **Improved error handling** with proper exception propagation
- **Better separation of concerns** between configuration, credentials, and sync logic
- **Consistent logging patterns** with structured debug information

### 📚 Documentation

#### User-Facing Documentation
- **Comprehensive troubleshooting guide** (`docs/troubleshooting-sync.md`) covering:
  - Common symptoms and quick fixes (setup hangs, authentication issues, network problems)
  - Step-by-step diagnostic procedures with copy-paste commands
  - Advanced recovery techniques including complete reset procedures
  - Professional issue reporting template with required debugging information
  - Prevention tips and maintenance best practices
- **Updated README** with troubleshooting guide link and quick health check commands
- **Enhanced command help text** with better descriptions and examples

### 🐛 Bug Fixes

#### Setup and Configuration
- **Fixed indefinite hang during interactive project mapping** - now has timeout and skip options
- **Resolved enum serialization in YAML config files** - no more Python object tags in config
- **Fixed AppSyncManager not loading configured providers** - status commands now work correctly
- **Improved keyring integration** with proper fallback to environment variables

#### Error Handling
- **Fixed timeout errors in non-interactive environments** - better environment detection
- **Improved network error handling** with retries and clear error messages  
- **Fixed authentication token validation** - better error reporting for invalid tokens
- **Enhanced configuration loading** - handles corrupt config files gracefully

### ⚡ Performance

- **Reduced setup time** with `--skip-mapping` option for users who don't need project mapping
- **Better timeout handling** prevents indefinite waits
- **Improved configuration loading** with lazy initialization where appropriate

### 🔒 Security

- **Enhanced credential security** - tokens never exposed in logs or error messages
- **Improved keyring integration** with secure fallback mechanisms
- **Better environment variable handling** with proper masking in debug output

### 💻 Developer Experience

- **Comprehensive test coverage** prevents regressions of the fixed issues
- **Improved debugging tools** with the new doctor command
- **Enhanced error messages** with actionable guidance
- **Better development workflow** with automated testing in CI

### 🎯 Migration Notes

#### For Existing Users
- **No breaking changes** - all existing configurations continue to work
- **Automatic config migration** - old YAML files with Python object serialization are handled gracefully
- **Recommended actions:**
  ```bash
  # Verify your setup is working correctly
  uv run todo app-sync doctor
  
  # Check status (should now show configured providers)
  uv run todo app-sync status
  
  # If you experience issues, see the troubleshooting guide
  # docs/troubleshooting-sync.md
  ```

#### For New Users
- **Setup is now more reliable** - use the new options for better experience:
  ```bash
  # Quick setup without project mapping
  export TODOIST_API_TOKEN="your_token"
  uv run todo app-sync setup todoist --skip-mapping
  
  # Verify everything is working
  uv run todo app-sync doctor
  ```

### 🙏 Acknowledgments

This release significantly improves the reliability and user experience of the app-sync functionality. The improvements are based on:
- Thorough analysis of setup hang issues
- Enhanced error handling and timeout management  
- Comprehensive testing to prevent regressions
- User-focused troubleshooting and documentation improvements

---

## [0.1.0] - 2025-09-16

### 🚀 Initial Release

#### Core Features
- **Full-featured todo management** with rich data models (40+ fields per task)
- **Advanced natural language parsing** - extract metadata from plain text
- **Multi-app synchronization** with Todoist integration
- **Project and context management** with flexible organization
- **Smart search and filtering** with query shortcuts
- **Export system** supporting multiple formats (JSON, CSV, Markdown, HTML, PDF, iCal, YAML)
- **Notification system** with desktop and email notifications
- **Calendar integration** with bidirectional sync capabilities
- **Recurring tasks** with intelligent pattern recognition

#### App Synchronization
- **Todoist adapter** with full bidirectional sync
- **Project and label mapping** between Todo CLI and external apps
- **Conflict resolution engine** with multiple strategies
- **Secure credential management** using system keyring
- **CLI commands** for complete sync management

#### Architecture
- **Clean, extensible architecture** with type safety throughout
- **Adapter pattern** for external app integrations
- **Robust storage system** using Markdown + YAML
- **Comprehensive configuration system** with YAML-based settings

#### Developer Experience
- **Modern Python tooling** with uv for dependency management
- **Comprehensive test suite** with pytest
- **Rich CLI interface** using Rich library for enhanced UX
- **Professional code quality** with type hints and clean architecture

---

For more details on any release, see the [GitHub releases page](https://github.com/Schaafd/todo_cli/releases).
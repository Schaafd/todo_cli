# Troubleshooting App Sync Issues

This guide helps you diagnose and fix common issues with the todo CLI app synchronization feature. Follow the steps in order for the best results.

## Quick Health Check

Start here if you're experiencing any sync issues:

```bash
# Verify your installation
uv run todo --version
uv run todo app-sync --help

# Check sync status
uv run todo app-sync status

# Run diagnostics
uv run todo app-sync doctor
```

## Common Symptoms and Solutions

### 🔄 Setup Hangs or Takes Forever

**Symptoms:**
- `todo app-sync setup todoist` never completes
- Terminal appears frozen during setup
- No progress indication after entering token

**Quick Fixes:**
1. **Use non-interactive mode:**
   ```bash
   export TODOIST_API_TOKEN="your_token_here"
   uv run todo app-sync setup todoist --no-interactive --skip-mapping
   ```

2. **Increase timeout:**
   ```bash
   uv run todo app-sync setup todoist --timeout 120
   ```

3. **Cancel and retry with debug:**
   ```bash
   # Press Ctrl+C to cancel, then:
   uv run todo app-sync setup todoist --debug
   ```

### ❌ "No providers configured" Message

**Symptoms:**
- `todo app-sync status` shows "No providers configured"
- Setup appeared to complete successfully
- Commands return empty results

**Solutions:**
1. **Check configuration file:**
   ```bash
   ls -la ~/.todo/
   cat ~/.todo/app_sync.yaml  # Should exist and contain provider config
   ```

2. **Verify credentials:**
   ```bash
   # Check environment variable
   echo $TODOIST_API_TOKEN
   
   # Run doctor to check keyring
   uv run todo app-sync doctor
   ```

3. **Re-run setup if config is missing:**
   ```bash
   uv run todo app-sync setup todoist --skip-mapping
   ```

### 🔑 Authentication/Token Issues

**Symptoms:**
- "Invalid token" or "Unauthorized" errors
- Setup fails during token validation
- Sync operations fail with 401 errors

**Solutions:**
1. **Get a fresh token:**
   - Go to [Todoist Integrations Settings](https://todoist.com/prefs/integrations)
   - Copy your API token
   - Use it in setup:
   ```bash
   uv run todo app-sync setup todoist --api-token "your_new_token"
   ```

2. **Clear old credentials and retry:**
   ```bash
   # Remove stored credentials
   rm -f ~/.todo/app_sync.yaml
   
   # Setup again
   export TODOIST_API_TOKEN="your_token"
   uv run todo app-sync setup todoist --no-interactive
   ```

### 🌐 Network Connectivity Issues

**Symptoms:**
- "Network error" or "Connection timeout"
- Setup fails with connection errors
- Doctor command reports network issues

**Solutions:**
1. **Check basic connectivity:**
   ```bash
   curl -I https://api.todoist.com/
   # Should return HTTP 200 or 302
   ```

2. **Test API access:**
   ```bash
   curl -H "Authorization: Bearer $TODOIST_API_TOKEN" \
        https://api.todoist.com/rest/v2/projects
   ```

3. **Check for proxy configuration:**
   ```bash
   env | grep -E "^HTTPS?_PROXY|^NO_PROXY"
   ```

4. **Use longer timeout:**
   ```bash
   uv run todo app-sync setup todoist --timeout 60
   ```

## Detailed Diagnostics

### Step 1: Verify Installation

```bash
# Check todo CLI version
uv run todo --version

# Verify app-sync commands are available
uv run todo app-sync --help

# Should show commands: setup, status, doctor, etc.
```

**Expected Output:** Version number and help text should display without errors.

### Step 2: Check Configuration Directory

```bash
# List config directory
ls -la ~/.todo

# Check permissions
stat ~/.todo
```

**What to Look For:**
- Directory should exist and be readable/writable by your user
- Look for `app_sync.yaml` file
- Check for any `.lock` files (remove if stale)

**Fix Permissions:**
```bash
chmod 700 ~/.todo
chmod 600 ~/.todo/app_sync.yaml  # if it exists
```

### Step 3: Examine Configuration File

```bash
# View current config
cat ~/.todo/app_sync.yaml
```

**Healthy Config Should Contain:**
```yaml
providers:
  todoist:
    name: todoist
    provider_type: todoist
    enabled: true
    settings:
      api_endpoint: https://api.todoist.com/rest/v2
```

**Fix Corrupt Config:**
```bash
# Backup and remove corrupt config
mv ~/.todo/app_sync.yaml ~/.todo/app_sync.yaml.backup
uv run todo app-sync setup todoist --skip-mapping
```

### Step 4: Debug Mode Investigation

Enable debug logging to see detailed information:

```bash
# Run with debug output
uv run todo app-sync status --debug

# Setup with debug (if needed)
uv run todo app-sync setup todoist --debug --skip-mapping
```

**Save Debug Logs:**
```bash
# Capture debug output to file
uv run todo app-sync doctor --debug 2>&1 | tee debug.log
```

### Step 5: Network Troubleshooting

**Test TLS Connection:**
```bash
openssl s_client -connect api.todoist.com:443 -servername api.todoist.com -brief
```

**Check DNS Resolution:**
```bash
nslookup api.todoist.com
dig api.todoist.com
```

**Corporate Network Issues:**
- Check if you're behind a corporate firewall
- Ask your IT team about access to `api.todoist.com`
- Consider using VPN if available

## Advanced Recovery Steps

### Complete Reset

If nothing else works, perform a complete reset:

```bash
# 1. Backup current config (optional)
cp -r ~/.todo ~/.todo.backup

# 2. Remove all app-sync configuration
rm -f ~/.todo/app_sync.yaml

# 3. Clear any cached credentials (varies by system)
# On macOS with Keychain:
security delete-generic-password -s "todo-cli" -a "todoist" 2>/dev/null || true

# 4. Fresh setup
export TODOIST_API_TOKEN="your_token"
uv run todo app-sync setup todoist --no-interactive --skip-mapping --timeout 60
```

### Environment Variable Setup

For non-interactive environments or CI/CD:

```bash
# Set token as environment variable
export TODOIST_API_TOKEN="your_actual_token_here"

# Verify it's set
echo "Token set: ${TODOIST_API_TOKEN:0:10}..."

# Run setup in non-interactive mode
uv run todo app-sync setup todoist --no-interactive --skip-mapping

# Verify setup worked
uv run todo app-sync status
```

### Manual Configuration

As a last resort, manually create the configuration:

```bash
# Create config directory
mkdir -p ~/.todo

# Create minimal config file
cat > ~/.todo/app_sync.yaml << 'EOF'
providers:
  todoist:
    name: todoist
    provider_type: todoist
    enabled: true
    settings:
      api_endpoint: https://api.todoist.com/rest/v2
EOF

# Set environment variable for token
export TODOIST_API_TOKEN="your_token_here"

# Test
uv run todo app-sync status
```

## When to File an Issue

If you've tried all the above steps and still have issues, please file a GitHub issue with the following information:

### Required Information

```bash
# 1. System information
uv --version
python --version
uname -a  # (on macOS/Linux)

# 2. Todo CLI version
uv run todo --version

# 3. Debug output
uv run todo app-sync doctor --debug > debug.log 2>&1

# 4. Configuration (redact any tokens)
ls -la ~/.todo/
cat ~/.todo/app_sync.yaml | sed 's/api_token:.*/api_token: [REDACTED]/'

# 5. Network connectivity test
curl -I https://api.todoist.com/ 2>&1

# 6. Environment variables (redact sensitive values)
env | grep -E "(PROXY|TODOIST)" | sed 's/=.*/=[REDACTED]/'
```

### Issue Template

Use this template when filing an issue:

```markdown
## Problem Description
Brief description of what's not working.

## Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## System Information
- OS: [e.g., macOS 14.0, Ubuntu 22.04]
- Python Version: [from `python --version`]
- uv Version: [from `uv --version`]  
- Todo CLI Version: [from `uv run todo --version`]

## Debug Output
```
[Paste debug.log contents here]
```

## Additional Context
Any other relevant information, special network setup, corporate environment, etc.
```

## Prevention Tips

### Regular Maintenance

```bash
# Weekly health check
uv run todo app-sync doctor

# Update dependencies occasionally
uv sync

# Check for new CLI versions
uv run todo --version
```

### Environment Best Practices

1. **Use environment variables** for tokens in automated environments
2. **Set reasonable timeouts** if you have slow network connections
3. **Use `--skip-mapping`** flag if you don't need project mapping
4. **Enable debug mode** when diagnosing issues

### Common Gotchas

- **Don't commit tokens** to version control
- **Tokens expire**: Get fresh ones from Todoist if setup suddenly stops working
- **Network proxies**: Corporate networks may block or modify API requests
- **File permissions**: The `~/.todo` directory must be writable by your user
- **Multiple Python environments**: Make sure you're running the CLI in the correct environment

---

## Need More Help?

- 📚 [Main Documentation](../README.md)
- 🐛 [File an Issue](https://github.com/Schaafd/todo_cli/issues)
- 💬 [Discussions](https://github.com/Schaafd/todo_cli/discussions)

---

*This guide covers the most common app-sync issues. For feature requests or general usage questions, please check the main documentation or start a discussion.*
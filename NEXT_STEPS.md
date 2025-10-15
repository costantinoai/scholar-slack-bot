# Next Steps - Priority Order

## IMMEDIATE: Fix Unresponsive UI

**Problem**: The new web UI is not clickable/selectable
**Root Cause**: CDN scripts (HTMX, Tailwind) may be blocked or not loading in your browser

**Solutions** (pick one):

### Option 1: Use Traditional Forms (Like old gui.py)
Convert the HTMX approach to traditional HTML forms with POST requests that trigger full page reloads. This is what made gui.py work.

### Option 2: Debug Browser Issues
- Check browser console for JavaScript errors (F12 → Console tab)
- Verify CDN scripts are loading (F12 → Network tab)
- Try a different browser
- Check if JavaScript is enabled

### Option 3: Hybrid Approach
Keep HTMX for dynamic updates but add traditional form fallbacks for critical actions.

---

## HIGH PRIORITY: Complete Slack Plugin

**File**: `plugins/slack/client.py`
**Error**: `No module named 'plugins.slack.client'`

**What Needs To Be Done**:

1. **Create `plugins/slack/client.py`** with `SlackPlugin` class that implements:
   - `send_message(message, channel)` - Send to Slack
   - `format_publications(pubs)` - Format for Slack
   - `test_connection()` - Verify Slack API token works
   - `get_config_schema()` - Define required config

2. **Plugin Architecture**:
   ```
   API ← → Plugin ← → Communication Channel
           (Slack)      (Slack API)
   ```

3. **Configuration**:
   - Read from `./src/slack.config` or `./config/slack.json`
   - Required: `api_token`, `default_channel`

4. **Test It**:
   ```bash
   # Via API
   curl -X POST http://localhost:8000/api/v1/plugins/slack/notify?message=Test

   # Via CLI (direct core access)
   python -c "from plugins.slack.client import SlackPlugin; \
              plugin = SlackPlugin({...}); \
              plugin.send_message('Test', '#channel')"
   ```

---

## MEDIUM PRIORITY: Additional Plugins

After Slack works, implement:
- Email plugin (`plugins/email/client.py`)
- Discord plugin (`plugins/discord/client.py`)
- Webhook plugin (`plugins/webhook/client.py`)

All follow the same `MessagingPlugin` interface defined in `plugins/base.py`.

---

## CLEANUP: Remove Obsolete Files

Once new UI works, remove old GUI:
```bash
rm gui.py
git rm gui.py
git commit -m "chore: remove obsolete Flask GUI (replaced by modern web dashboard)"
```

---

## Architecture Recap

```
┌─────────────────────────────────────────┐
│           User Interfaces               │
├─────────────┬───────────────┬───────────┤
│  CLI (Typer)│ Web Dashboard │  Scripts  │
│   Direct    │   Via API     │  Via API  │
└──────┬──────┴───────┬───────┴─────┬─────┘
       │              │             │
       ▼              ▼             ▼
┌──────────────────────────────────────────┐
│           Core Logic (Database,          │
│           Fetcher, Config)               │
└─────────────┬────────────────────────────┘
              │
       ┌──────▼────────┐
       │  Plugin System │
       └───┬────────┬───┘
           │        │
      ┌────▼───┐ ┌─▼──────┐
      │ Slack  │ │ Email  │ ...
      │ Plugin │ │ Plugin │
      └────┬───┘ └─┬──────┘
           │       │
      ┌────▼───┐ ┌▼───────┐
      │ Slack  │ │ SMTP   │
      │  API   │ │ Server │
      └────────┘ └────────┘
```

**Key Point**: Plugins are the "man in the middle" between:
- **Input**: API/CLI calls the plugin
- **Output**: Plugin sends to communication channel (Slack, Email, etc.)

---

## Quick Wins

While debugging UI:
1. ✅ **start.sh created** - Run with `./start.sh`
2. ✅ **API working** - http://localhost:8000/docs
3. ✅ **Database working** - 62 authors, 324 publications
4. ⚠️ **Slack plugin** - Needs implementation
5. ⚠️ **UI clickability** - Needs fix

---

## Testing the Current API

Even if UI doesn't work, the API is fully functional:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Get authors
curl http://localhost:8000/api/v1/authors

# Add author
curl -X POST http://localhost:8000/api/v1/authors \
  -H "Content-Type: application/json" \
  -d '{"scholar_id": "abc123"}'

# Get publications
curl "http://localhost:8000/api/v1/publications?min_year=2024&limit=10"
```

---

## Recommendation

**Priority 1**: Fix Slack plugin (it's blocking notifications)
**Priority 2**: Fix UI clickability or fallback to traditional forms
**Priority 3**: Clean up old files once new system works

Would you like me to:
1. Implement the Slack plugin first? ✅ **RECOMMENDED**
2. Fix the UI by converting to traditional forms?
3. Debug the current HTMX approach?

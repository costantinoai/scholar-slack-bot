# Slack Bot for Google Scholar Publications

This Slack Bot fetches publications for authors from Google Scholar and sends notifications to a specified Slack channel or user. Keep your team updated with the latest scholarly articles seamlessly!  

---

## 🚀 Quick Start  

1. **Clone the repository:**  
   ```sh
   git clone https://github.com/costantinoai/scholar-slack-bot.git
   cd scholar-slack-bot
   ```  
2. **Install dependencies:**  
   ```sh
   pip install -r requirements.txt
   ```  
3. **Edit the config file:**  
   - Add your Slack API token.  
   - Set the `target_name` field to either a **Slack channel** (public or private, if the bot is added) or a **Slack user** (for direct messages).  
   - Refer to the section [Setting Up Your Slack Bot](#setting-up-your-slack-bot) below for instructions on obtaining the Slack API token.  
4. **Run the bot:**
   ```sh
   python main.py fetch
   ```
   Other subcommands provide testing and maintenance workflows:

   ```sh
   python main.py send                 # send a test message
   python main.py test-fetch <ID>      # fetch an author without saving
   python main.py update-cache         # refresh cache only
   python main.py test-run             # dry run for two authors
   ```

---

## 📚 Table of Contents  

1. [🔧 Setting Up The Repo](#setting-up-the-repo)  
2. [🤖 Setting Up Your Slack Bot](#setting-up-your-slack-bot)  
3. [🚀 Usage](#usage)  
4. [📂 Directory Structure](#directory-structure)  
5. [📝 Files Descriptions](#files-descriptions)  
6. [📄 License](#license)  

---

## 🔧 Setting Up The Repo  

Clone the repository:  

```sh
git clone https://github.com/costantinoai/scholar-slack-bot.git
cd scholar-slack-bot
```

Install dependencies:

```sh
pip install -r requirements.txt
```


Edit `slack.config` with your bot’s API token and target name:  

```ini
[slack]
api_token = xoxb-YOUR-API-TOKEN
channel_name = YOUR-TARGET-NAME  # Can be a channel (e.g., "general") or a user (e.g., "john_doe")
```

If a **Slack channel name** (e.g., `weekly-papers-update`) is provided, the bot will post there.
If a **Slack user name** is provided (e.g., `Andrea Costantino`), the bot will send a direct message.

Add author details to `src/authors.db`.

Legacy JSON caches (`authors.json` and per-author files under `googleapi_cache`) are
detected automatically on startup. When present, their contents are imported into
the SQLite databases and the original files are moved to `src/obsolete` for
archival.

---

## 🤖 Setting Up Your Slack Bot  

### 1. Create a Slack App  

1. Go to the [Slack API's "Your Apps" page](https://api.slack.com/apps).  
2. Click **Create New App**.  
3. Name your app, select a development workspace, and click **Create App**.  

### 2. Add a Bot User  

1. In your app's settings, go to **Bot Users** and click **Add a Bot User**.  
2. Name your bot and enable it to be always online.  

### 3. Permissions & Scopes  

Slack apps require specific permissions (scopes) to function. Navigate to **OAuth & Permissions** in your app settings and add these bot token scopes:  

- `channels:read` - View public channels in the workspace.  
- `chat:write` - Send messages to channels and users.  
- `groups:read` - View private channels where the bot has been added.  
- `im:write` - Send direct messages to users.  
- `mpim:write` - Send group direct messages.  
- `users:read` - View user profiles in the workspace.  

### 4. Get Your API Token  

1. In **OAuth & Permissions**, find the **OAuth Tokens for Your Workspace** section.  
2. Copy the token (starts with `xoxb-`).  
3. Save it securely. Never commit this token to a public repository.  

### 5. Invite the Bot to a Channel  

1. In Slack, navigate to the target channel.  
2. Click the channel name → **Add people & bots**.  
3. Search for your bot’s name and invite it.  

---

## 🚀 Usage  

### Command Line

The CLI now uses **subcommands** instead of boolean flags. Global options may be
placed before the subcommand:

```sh
python main.py [--authors_path PATH] [--slack_config_path PATH] [--verbose] <command> [args]
```

Available subcommands:

| Command | Fetches Data | Sends Message | Saves to Cache | Notes |
|---------|--------------|---------------|----------------|-------|
| `fetch` | ✅ | ✅ | ✅ | Default workflow for all authors. |
| `send` | ❌ | ✅ | ❌ | Send a connectivity test message only. |
| `add-author SCHOLAR_ID` | ✅ | ❌ | ✅ | Add a scholar and store their publications. |
| `update-cache` | ✅ | ❌ | ✅ | Refresh publications for every author. |
| `test-fetch SCHOLAR_ID` | ✅ | ❌ | ❌ | Fetch one author without side effects. |
| `test-run [--limit N]` | ✅ | ✅ | ❌ | Dry run for `N` authors (default 2). |

Examples use the format `python main.py <command> [args]`.

Global options include:

- `--authors_path`: Path to the authors database. Default: `./src/authors.db`.
- `--slack_config_path`: Path to `slack.config`. Default: `./src/slack.config`.
- `--verbose`: Enable verbose logging output.


### Web Interface (FastAPI + HTMX)

Run the API + Web UI with Uvicorn:

```bash
python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 and use the left menu:

- Dashboard: overview charts and quick actions
- Authors: manage monitored authors (Scholar/OpenAlex/ORCID), refresh cache, preview & send
- Publications: browse/filter cached publications; open links; deduplicated grouped variants
- Plugins: configure Slack plugin and test connectivity
- Settings: select backend (OpenAlex/Scholar), connectivity tests, hard reset in background
- Stats: deep statistics (year trends, top journals, keywords, h-index)

---

## 📂 Directory Structure (FastAPI)

```
scholar-slack-bot/
├── src/
│   ├── api/                  # FastAPI app (routes, models, deps)
│   ├── web/                  # Jinja2 templates, routes, static (HTMX+Chart.js)
│   ├── openalex/             # OpenAlex client + persistence helpers
│   ├── publications.db       # SQLite cache of publications
│   ├── authors.db            # SQLite database of monitored authors
│   └── slack.config          # Slack plugin config (gitignored example provided)
├── plugins/                  # Plugin system (Slack implemented)
├── tests/                    # Unit tests (no real tokens used)
├── main.py                   # Legacy CLI (fetch/send; still supported)
├── fetch_scholar.py          # Scholar backend (optional if using OpenAlex)
├── helper_funcs.py           # Legacy utilities (CLI compatibility)
├── requirements.txt
├── settings.json             # UI settings
└── README.md
```

---

## 📝 Key Files

### Core Application Files
- **`main.py`**: CLI entry point with subcommand-based interface
- **`fetch_scholar.py`**: Google Scholar API interactions and data fetching
- **`slack_bot.py`**: Slack message formatting and API communication
- **`streams_funcs.py`**: Workflow orchestration for different command modes
- **`helper_funcs.py`**: Utility functions (database operations, cache management)
- **`log_config.py`**: Centralized logging configuration
- **`gui.py`**: Flask web interface for visual management

### Configuration Files
- **`src/slack.config`**: Slack API credentials and channel configuration
  ```ini
  [slack]
  api_token = xoxb-YOUR-API-TOKEN
  channel_name = your-channel-or-user  # Channel name or direct message target
  ```
  💡 *No channel ID needed — the bot auto-detects channels vs. users*

- **`settings.json`**: GUI persistent settings (database paths, API delay, etc.)
- **`pytest.ini`**: Test framework configuration

### Database Files
- **`src/authors.db`**: SQLite database storing monitored authors (name + Google Scholar ID)
- **`src/publications.db`**: SQLite cache of fetched publications with metadata

### Testing
- **`tests/`**: Comprehensive test suite including:
  - Golden tests (mocked + real API integration)
  - GUI tests (Flask routes and actions)
  - Workflow tests (command orchestration)
  - Unit tests (individual modules)

### Automation Scripts (Optional)
- **`add_authors_batch.sh`**: Batch add multiple authors via CLI
- **`fetch_and_send.sh`**: Run full workflow (useful for cron jobs)  

---

## 🐳 Docker

Build and run the API + Web UI with Docker:

```bash
docker build -t scholar-slack-bot .
docker run --rm -p 8000:8000 \
  -v $(pwd)/src:/app/src \
  --name scholar-bot scholar-slack-bot
```

Visit http://localhost:8000 to access the dashboard.

Notes:
- The `-v $(pwd)/src:/app/src` mount persists `authors.db`, `publications.db`, and `settings.json`.
- Configure OpenAlex `mailto` and backend in Settings after the container starts.

---

## 📄 License  

[MIT](LICENSE) © Andrea Ivan Costantino  

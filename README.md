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
   The package lives under `src/`. Either install it in editable mode or point
   `PYTHONPATH` at that directory when invoking the CLI:

   ```sh
   PYTHONPATH=src python -m scholar_slack_bot
   ```
   The helper scripts under `scripts/` configure this automatically, so you can
   run `./scripts/fetch_and_send.sh` from any directory.
   A similar wrapper `./scripts/run_gui.sh` launches the web interface.

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

Add author details to `data/authors.db`.

Legacy JSON caches (`authors.json` and per-author files under `googleapi_cache`) are
detected automatically on startup. When present, their contents are imported into
the SQLite databases and the original files are moved to `data/obsolete` for
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

The script accepts several command-line arguments (flags) to customize its behavior:

- `--authors_path`: Specifies the path to the authors database.
  - Default: `data/authors.db` relative to the project root

- `--slack_config_path`: Sets the path to the `slack.config` file which contains Slack API token and channel information.
  - Default: `data/slack.config` relative to the project root

- `--verbose`: (Optional) Provides verbose output for detailed logging and debugging.

- `--test_message`: (Optional) Send test message. Do not fetch or save cache. Mutually exclusive with `--add_scholar_id` and `--update_cache`.
  - Example:
  ```python -m scholar_slack_bot --test_message```

- `--add_scholar_id`: (Optional) Add a new scholar by Google Scholar ID to the file specified in `--authors_path`, fetch publications and save them to cache (do not send message). Mutually exclusive with `--test_message` and `--update_cache`.
  - Example:
  ```python -m scholar_slack_bot --add_scholar_id="YourGoogleScholarID"```

- `--update_cache`: (Optional) Re-fetch and save publications for all authors (do not send message). It overwrites the old cache. Mutually exclusive with `--test_message` and `--add_scholar_id`.
  - Example:
  ```python -m scholar_slack_bot --update_cache```


### Within the IDE

When launching from an IDE, supply arguments via your run configuration. The
defaults defined in the CLI are applied when no explicit arguments are passed.

### Web Interface

A modern Flask web UI is bundled for managing the bot. Launch it with the
helper script which configures the environment automatically:

```sh
./scripts/run_gui.sh
```

The responsive page at [http://localhost:5000](http://localhost:5000) offers:

- Author tools: add/remove authors, refresh or clear their cache.
- Publication browser: view cached papers in a searchable table.
- Settings editor: adjust database locations, Slack config path, and API call delay. Changes are saved to `data/settings.json` for future runs.
- Utilities: clear all cache and run the project's tests. Destructive actions prompt for confirmation.

---

## 📂 Directory Structure  

```
scholar-slack-bot
├── data
│   ├── authors.db
│   ├── publications.db
│   ├── settings.json
│   └── slack-example.config
├── scripts
│   ├── add_authors_batch.sh
│   ├── fetch_and_send.sh
│   └── run_gui.sh
├── src
│   └── scholar_slack_bot
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── scholar
│       │   ├── __init__.py
│       │   └── fetch.py
│       ├── workflow
│       │   ├── __init__.py
│       │   └── pipeline.py
│       ├── slack
│       │   ├── __init__.py
│       │   └── client.py
│       ├── ui
│       │   ├── __init__.py
│       │   └── gui.py
│       └── utils
│           ├── __init__.py
│           ├── helpers.py
│           └── logging.py
├── pyproject.toml
├── README.md
```

---

## 📝 Files Descriptions  

- **`scripts/add_authors_batch.sh`**: Bash script for batch-adding authors from a file. Automatically sets `PYTHONPATH`.
- **`scripts/fetch_and_send.sh`**: Bash script to run the bot workflow. Automatically sets `PYTHONPATH`.
- **`scholar/fetch.py`**: Internal functions to fetch publications from Google Scholar.
- **`ui/gui.py`**: Flask web application for author management and settings.
- **`utils/helpers.py`**: Internal utility functions.
- **`utils/logging.py`**: Internal logging configuration.
- **`cli.py`**: Command-line interface for running the bot.
- **`slack/client.py`**: Internal functions to format and send messages to Slack.
- **`workflow/pipeline.py`**: Orchestrates workflow logic based on CLI flags.
- **`data/authors.db`**: SQLite database storing author names and Google Scholar IDs.

- **`data/publications.db`**: SQLite database caching publication data.
- **`data/slack-example.config`**: Sample configuration file for Slack settings. Example format:
- **`data/settings.json`**: Persistent options used by the GUI (database paths, API delay, etc.).
- **`pyproject.toml`**: Package metadata and build configuration.

  ```ini
  [slack]
  api_token = xoxb-YOUR-API-TOKEN
  channel_name = your-channel-or-user
  ```

💡 *You do not need to specify a channel ID — the bot will automatically determine whether `channel_name` refers to a public/private channel or a user.*  

---

## 📄 License  

[MIT](LICENSE) © Andrea Ivan Costantino  


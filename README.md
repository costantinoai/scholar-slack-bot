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
   python main.py
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

The script accepts several command-line arguments (flags) to customize its behavior:

- `--authors_path`: Specifies the path to the authors database.
  - Default: `./src/authors.db`

- `--slack_config_path`: Sets the path to the `slack.config` file which contains Slack API token and channel information.
  - Default: `./src/slack.config`

- `--verbose`: (Optional) Provides verbose output for detailed logging and debugging.

- `--test_message`: (Optional) Send test message. Do not fetch or save cache. Mutually exclusive with `--add_scholar_id` and `--update_cache`.
  - Example:
  ```python main.py --test_message```

- `--add_scholar_id`: (Optional) Add a new scholar by Google Scholar ID to the file specified in `--authors_path`, fetch publications and save them to cache (do not send message). Mutually exclusive with `--test_message` and `--update_cache`.
  - Example:
  ```python main.py --add_scholar_id="YourGoogleScholarID"```

- `--update_cache`: (Optional) Re-fetch and save publications for all authors (do not send message). It overwrites the old cache. Mutually exclusive with `--test_message` and `--add_scholar_id`.
  - Example:
  ```python main.py --update_cache```


### Within the IDE  

If running from an IDE (e.g., Spyder, VScode), configurations are set in `IDEargs` in `main.py`. Modify paths or debug settings as needed.  

---

## 📂 Directory Structure  

```
slack-bot
├── add_authors_batch.sh
├── fetch_and_send.sh
├── fetch_scholar.py
├── helper_funcs.py
├── log_config.py
├── main.py
├── README.md
├── slack_bot.py
├── streams_funcs.py
└── src
    ├── authors.db
    ├── publications.db
    └── slack.config
```

---

## 📝 Files Descriptions  

- **`add_authors_batch.sh`**: Bash script for batch-adding authors.  
- **`fetch_and_send.sh`**: Bash script to run the bot workflow.  
- **`fetch_scholar.py`**: Internal functions to fetch publications from Google Scholar.  
- **`helper_funcs.py`**: Internal utility functions.  
- **`log_config.py`**: Internal Logging configuration.  
- **`main.py`**: The main script to run the bot.  
- **`slack_bot.py`**: Internal functions to format and send messages to Slack.  
- **`streams_funcs.py`**: Internal, handles workflow logic based on CLI flags.  
- **`authors.db`**: SQLite database storing author names and Google Scholar IDs.

- **`publications.db`**: SQLite database caching publication data.
- **`slack.config`**: Configuration file for Slack settings. Example format:  

  ```ini
  [slack]
  api_token = xoxb-YOUR-API-TOKEN
  channel_name = your-channel-or-user
  ```

💡 *You do not need to specify a channel ID — the bot will automatically determine whether `channel_name` refers to a public/private channel or a user.*  

---

## 📄 License  

[MIT](LICENSE) © Andrea Ivan Costantino  


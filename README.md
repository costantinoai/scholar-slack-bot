# Slack Bot for Google Scholar Publications

This Slack Bot fetches publications for authors from Google Scholar and sends notifications to a specified Slack channel or user. Keep your team updated with the latest scholarly articles seamlessly!  

---

## 🚀 Quick Start

1. **Clone the repository**
   ```sh
   git clone https://github.com/costantinoai/scholar-slack-bot.git
   cd scholar-slack-bot
   ```
2. **Install the package**
   ```sh
   pip install -e .
   ```
3. **Configure Slack credentials**
   - Copy `.env.example` to `.env` and fill in your Slack token and target channel/user.
   - See [Setting Up Your Slack Bot](#setting-up-your-slack-bot) for details on obtaining a token.
4. **Run the bot**
   ```sh
   scholar-slack-bot --verbose
   ```

---

## 📚 Table of Contents  

1. [🔧 Setting Up The Repo](#setting-up-the-repo)  
2. [🤖 Setting Up Your Slack Bot](#setting-up-your-slack-bot)  
3. [🚀 Usage](#usage)  
4. [📂 Directory Structure](#directory-structure)  
5. [📝 Files Descriptions](#files-descriptions)  
6. [🛣️ Roadmap & Tasks](#roadmap--tasks)
7. [📄 License](#license)

---

## 🔧 Setting Up The Repo  

Clone the repository and install in editable mode:

```sh
git clone https://github.com/costantinoai/scholar-slack-bot.git
cd scholar-slack-bot
pip install -e .
```

Create a `.env` file with your Slack credentials:

```sh
cp .env.example .env
# edit .env and set SLACK_API_TOKEN and SLACK_CHANNEL
```

Add author details in `src/authors.json` as shown below.

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

- `--authors_path`: Specifies the path to the `authors.json` file.
  - Default: `./src/authors.json`

- `--slack_config_path`: Sets the path to the `slack.config` file which contains Slack API token and channel information.
  - Default: `./src/slack.config`

- `--verbose`: (Optional) Provides verbose output for detailed logging and debugging.

- `--test_fetching`: (Optional) Test fetching functions. Do not send message (unless --test_message) or save cache. Mutually exclusive with `--add_scholar_id` and `--update_cache`.
  - Example (fetch only):
  Fetch last year's data for two authors in `./src/authors.json`. Do not send messages or update cache.
  ```python main.py --test_fetching```
  
  - Example (fetch and send message)
  Fetch last year's data for two authors in `./src/authors.json`. Send messages with fetched papers, but do not update cache.
  ```python main.py --test_fetching --test_message```

- `--test_message`: (Optional) Send test message. Do not fetch, send message (unless --test_fetching) or save cache. Mutually exclusive with `--add_scholar_id` and `--update_cache`.
  - Example:
  ```python main.py --test_message```

- `--add_scholar_id`: (Optional) Add a new scholar by Google Scholar ID to the file specified in `--authors_path`, fetch publications and save them to cache (do not send message). Mutually exclusive with `--test_message`, `--test_fetching` and `--update_cache`.
  - Example:
  ```python main.py --add_scholar_id="YourGoogleScholarID"```

- `--update_cache`: (Optional) Re-fetch and save publications for all authors (do not send message). It overwrites the old cache. Mutually exclusive with `--test_message`, `--test_fetching` and `--add_scholar_id`.
  - Example:
  ```python main.py --update_cache```


### Within the IDE  

If running from an IDE (e.g., Spyder, VScode), configurations are set in `IDEargs` in `main.py`. Modify paths or debug settings as needed.  

---

## 📂 Directory Structure  

```
scholar-slack-bot
├── scholar_slack_bot
│   ├── __init__.py
│   ├── fetch_scholar.py
│   ├── helper_funcs.py
│   ├── log_config.py
│   ├── main.py
│   ├── slack_bot.py
│   └── streams_funcs.py
├── add_authors_batch.sh
├── fetch_and_send.sh
├── pyproject.toml
├── requirements.txt
└── src
    ├── authors.json
    └── slack-example.config
```

---

## 📝 Files Descriptions

- **`add_authors_batch.sh`**: Example shell script for adding multiple authors.
- **`fetch_and_send.sh`**: Example shell script to run the bot.
- **Package `scholar_slack_bot/`**: contains the Python modules
  - `main.py`: command line entry point
  - `fetch_scholar.py`: fetch publications from Google Scholar
  - `slack_bot.py`: format and send Slack messages
  - `streams_funcs.py`: workflow helpers
  - `helper_funcs.py` and `log_config.py`: utilities
- **`authors.json`**: Stores author names and Google Scholar IDs. Example format:

  ```json
  [
      {"name": "Daniel Kaiser", "id": "v4CvWHgAAAAJ"},
      {"name": "Stefania Bracci", "id": "ECBBsv8AAAAJ"}
  ]
  ```

- **`.env.example`**: Template for environment variables. Copy to `.env` and fill in credentials.

💡 *You do not need to specify a channel ID — the bot will automatically determine whether `channel_name` refers to a public/private channel or a user.*

---

## 🛣️ Roadmap & Tasks

- Add asynchronous requests to improve performance when sending messages.
- Provide Docker image for easier deployment.
- Support additional scholarly sources beyond Google Scholar.
- Store cached publications in a database backend.
- Extend command-line interface with subcommands for cache management.

---

## 📄 License

[MIT](LICENSE) © Andrea Ivan Costantino  


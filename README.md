# 🌟 Slack Bot for Google Scholar Publications 🌟

This Slack Bot fetches publications for authors from Google Scholar and sends notifications to a specified Slack channel with details of the latest publications. Keep your team updated with the latest scholarly articles seamlessly!

## 📚 Table of Contents
1. [🤖 Setting Up Your Slack Bot](#setting-up-your-slack-bot)
2. [📚 Installing Required Libraries](#installing-libraries)
3. [🔧 Setting Up The Repo](#setting-up-the-repo)
4. [🚀 Usage](#usage)
5. [📂 Directory Structure](#directory-structure)
6. [📝 Files Descriptions](#files-descriptions)
7. [📄 License](#license)

## 🤖 Setting Up Your Slack Bot

### 1. Create a Slack App

1. Go to the [Slack API's "Your Apps" page](https://api.slack.com/apps).
2. Click the **Create New App** button.
3. Name your app, select the development workspace you want to use (you can create a new workspace if needed), and then click **Create App**.

### 2. Add Bot User

1. In your app's settings, go to the **Bot Users** feature and click **Add a Bot User**.
2. Name your bot and enable it to be always online.

### 3. Permissions & Scopes

Slack apps use scopes to request specific sets of permissions. To send messages to channels, the bot needs particular scopes.

1. Navigate to the **OAuth & Permissions** page in your app settings.
2. Under the **Scopes** section, add the following bot token scopes:
   - `channels:read` - To view basic information about public channels in the workspace.
   - `chat:write` - To send messages to channels.

It's essential to only request the permissions necessary for your bot to function, following the principle of least privilege.

### 4. Get Your API Token

1. Still on the **OAuth & Permissions** page.
2. Under the **OAuth Tokens for Your Workspace** section, you'll see a token that starts with `xoxb-`. This is your bot's API token.
3. Save this token securely. You'll need it for your `slack.config` file. Remember, never commit this token to public repositories for security reasons.

### 5. Invite Bot to Channel

1. Go to your Slack workspace.
2. Navigate to the channel you want the bot to post messages in.
3. Click on the channel name at the top, and select **Add people & bots**.
4. Search for your bot's name and invite it.

## 📚 Installing Required Libraries

Before you can run the project, you need to install some necessary libraries. To install the necessary libraries using `pip`, you can run the following commands:

```sh
pip install scholarly tqdm requests configparser
```

## 🔧 Setting Up The Repo

Clone this repository:
   ```sh
   git clone costantinoai/scholar-slack-bot
   cd scholar-slack-bot
   ```

Ensure you have all required dependencies installed:
   ```sh
   pip install -r requirements.txt
   ```

Now, populate `slack.config` file with your bot's API token, channel name, and channel ID. The structure should look like:

```ini
[slack]
api_token = xoxb-YOUR-API-TOKEN
channel_name = YOUR-CHANNEL-NAME
```

Add author details in `src/authors.json` or `src/authors_short.json`.

With everything set up, you can now run the code. The bot will send messages to the Slack channel based on the fetched publications.

## 🚀 Usage

### Command Line:

#### Flags

The script accepts several command-line arguments (flags) to customize its behavior:

- `--authors_path`: Specifies the path to the `authors.json` file.
  - Default: `./src/authors.json`
  - Example: 
  ``python main.py --authors_path="./path/to/your/authors.json"``

- `--slack_config_path`: Sets the path to the `slack.config` file which contains Slack API token and channel information.
  - Default: `./src/slack.config`
  - Example: 
  ```python main.py --slack_config_path="./path/to/your/slack.config"```

- `--verbose`: (Optional) Provides verbose output for detailed logging and debugging.
  - Example:
  ```python main.py --verbose```

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

### Within the IDE:

If you're running the script from an IDE, the default settings are taken from hardcoded configurations in the `IDEargs` class in the `main()` function of `main.py`. If you need to adjust paths or enable the debug mode for IDE execution, modify the corresponding variables in the `main()` function.

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
    ├── authors.json
    ├── googleapi_cache
    └── slack.config

```

## 📝 Files Descriptions

- **add_authors_batch.sh**: Bash script to add authors in batch. You need to set the correct `ids`, conda environment and conda.sh path to use this script.
- **fetch_and_send.sh**: Bash script to run the main workflow with default flags. You need to set the correct conda environment and conda.sh path to use this script.
- **fetch_scholar.py**: Functions to fetch comprehensive details for scholarly publications.
- **helper_funcs.py**: Collection of helper functions.
- **log_config.py**: Set logging levels for all the scripts.
- **main.py**: The main script. Run this file from terminal or IDE to run the bot.
- **slack_bot.py**: Functions to connect to format and send messages to a Slack channel.
- **streams_funcs.py**: Functions for every branch/scenario in main.py (depending on the active flags).
- **authors.json**: A file containing the list of authors' names and their corresponding Google Scholar IDs. Here's how you should structure the contents:

  ```json
  [
      {"name": "Daniel Kaiser", "id": "v4CvWHgAAAAJ"},
      {"name": "Stefania Bracci", "id": "ECBBsv8AAAAJ"}
  ]

- **authors.json**: Similar to `authors.json`, but with less authors and few missing publications. For debug purpose only (see Usage -> Flags -> `--debug` )
- **googleapi_cache**: A directory that caches publication data fetched from Google Scholar for each author. This helps in speeding up subsequent fetches and reduces unnecessary API calls.
- **slack.config**: Configuration file that contains Slack-related settings such as the API token and channel details. Make sure to structure the contents as:
	```ini
	[slack]
	api_token = xxx-xxxxxxxxxx
	channel_name = your-channel-name
	channel_id = optional-ch-id
	```
Always remember to keep your slack.config file secure and never commit sensitive data, like your API token, directly to public repositories.

Want to know more about each function? Check out their respective files for in-depth comments!

## 📄 License

[MIT](LICENSE) © Andrea Ivan Costantino



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
   - `chat:write.customize` - To send messages as the bot with a customized username and avatar, if needed.

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

Now, the file `slack.config` file with your bot's API token, channel name, and channel ID. The structure should look like:

```ini
[slack]
api_token = xoxb-YOUR-API-TOKEN
channel_name = YOUR-CHANNEL-NAME
```

Add author details in `src/authors.json` or `src/authors_short.json`.


Now, update the `slack.config` file with your bot's API token, channel name, and channel ID. The structure should look like:

```ini
[slack]
api_token = xoxb-YOUR-API-TOKEN
channel_name = YOUR-CHANNEL-NAME
channel_id = YOUR-CHANNEL-ID
```

With everything set up, you can now run the code. The bot will send messages to the Slack channel based on the fetched publications.

## 🚀 Usage

### Command Line:

#### Flags

The script accepts several command-line arguments (flags) to customize its behavior:

- `--authors_path`: Specifies the path to the `authors.json` file.
  - Default: `./src/authors_short.json`
  - Example: 
  ```sh
  python main.py --authors_path="./path/to/your/authors.json"
  ```

- `--slack_config_path`: Sets the path to the `slack.config` file which contains Slack API token and channel information.
  - Default: `./src/slack.config`
  - Example: 
  ```sh
  python main.py --slack_config_path="./path/to/your/slack.config"
  ```

- `--debug`: Enables debug mode which has specific behaviors intended primarily for testing the fetching mechanism of the bot.
  - Sets logging to STANDARD (higher) level.
  - Utilizes the `authors_short.json` file which contains only two authors with missing publications to speed up and simplify tests.
  - When saving fetched data, only cached data is stored, ensuring that updated data isn't saved. This ensures that on each call, the bot has to fetch and send something to Slack, allowing for repeated testing of the fetching mechanism.
  - Example:
  ```sh
  python main.py --debug
  ```

### Within the IDE:

If you're running the script from an IDE, the default settings are taken from hardcoded configurations in the `main()` function of `main.py`. If you need to adjust paths or enable the debug mode for IDE execution, modify the corresponding variables in the `main()` function.

## 📂 Directory Structure

```
slack-bot
├── fetch_scholar.py
├── helper_funcs.py
├── main.py
├── README.md
├── slack_bot.py
└── src
    ├── authors.json
    ├── authors_short.json
    ├── googleapi_cache
    └── slack.config

```

## 📝 Files Descriptions

- **fetch_scholar.py**: Functions to fetch comprehensive details for scholarly publications.
- **helper_funcs.py**: Collection of helper functions.
- **slack_bot.py**: Functions to connect to format and send messages to a Slack channel.
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



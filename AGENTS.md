# AGENTS Guidelines

## Development Workflow
- Format code with [`black`](https://black.readthedocs.io/en/stable/) and lint with [`flake8`](https://flake8.pycqa.org/). Run:
  ```bash
  black .
  flake8 .
  ```
- Run unit tests before committing:
  ```bash
  pytest
  ```
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages (e.g., `feat:`, `fix:`, `docs:`).

## Adding Authors
- Add new authors to `src/authors.json`.
- For single additions use:
  ```bash
  python main.py --add_scholar_id="SCHOLAR_ID"
  ```
- For batch additions use:
  ```bash
  ./add_authors_batch.sh path/to/file_with_ids.txt
  ```
- After modifying authors, run tests and commit the updated file.

## Running the Bot
- Copy `src/slack-example.config` to `src/slack.config` and fill in your Slack API token and channel/user.
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- Run the bot:
  ```bash
  python main.py
  ```
  or
  ```bash
  ./fetch_and_send.sh
  ```

## Handling Secrets
- Never commit API tokens or other secrets.
- Keep secrets in `src/slack.config` (ignored by Git) or environment variables.
- Avoid printing or sharing sensitive values.

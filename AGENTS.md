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

## Code Style and Documentation
- Include generous inline comments. Every logical step or block should have a comment that explains *why* the code exists and what it is doing.
- Provide docstrings for all modules, classes, and functions.
  - Describe the overall purpose, parameters, return values, side effects, and raised exceptions.
  - Use complete sentences and include type hints when possible.
- Example function with documentation and comments:
  ```python
  def process(data: list[str]) -> dict:
      """Process raw strings into a keyed dictionary.

      Args:
          data: Raw lines from the feed.

      Returns:
          Mapping of identifiers to parsed entries.

      Raises:
          ValueError: If the input data is malformed.
      """
      result = {}
      for line in data:
          # Split each line on commas to extract fields
          parts = line.split(',')
          # Ensure each line has exactly three parts: id, name, value
          if len(parts) != 3:
              raise ValueError(f"Bad line format: {line}")
          # Assign parsed values into the result dictionary
          result[parts[0]] = {"name": parts[1], "value": parts[2]}
      return result
  ```
- Prefer clarity over brevity: comment liberally to aid future maintainers.

## Adding Authors
- Add new authors to `src/authors.db` using the provided CLI utilities.
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

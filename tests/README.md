# Tests

This directory contains unit tests for the core functionality of the Scholar Slack Bot.

## What is covered
- **Publication cleaning (`clean_pubs`)** – verifies that old papers, uncited works, and duplicates are filtered out correctly.
- **Slack message formatting (`make_slack_msg`)** – ensures duplicate articles are deduplicated and that empty publication lists are handled.
- **Slack channel lookup (`get_channel_id_by_name`)** – mocks the Slack API to confirm that known channels are found and missing channels return `None`.
- **Message delivery (`send_to_slack`)** – checks that messages are sent to channels when available, fall back to user DMs when needed, and handle invalid recipients.
- **Author utilities** – cover tuple conversion, output-folder creation, adding authors to JSON, and argument conflict detection.
- **Cache workflows** – validate loading existing entries, combining fetched and cached publications, and promoting temporary cache directories.
- **Fetch workflows** – ensure `get_pubs_to_fetch` respects the `test_fetching` flag, `fetch_publications_by_id` skips cache writes when testing, and `fetch_pubs_dictionary` limits authors in test mode.

## Running tests
Run all tests locally with:

```bash
pytest
```

## Automatic testing on commit
The repository uses a [pre-commit](https://pre-commit.com/) hook to run `pytest` before each commit. Enable it with:

```bash
pip install pre-commit
pre-commit install
```

After installation, `pytest` will run automatically whenever you `git commit`, preventing commits if tests fail.

## Continuous Integration

GitHub Actions runs the full test suite for every pull request and for pushes to the `main` branch. The workflow prints
verbose test results so each test's status is visible in the build logs.

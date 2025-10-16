# AGENTS Guidelines

## Environment Setup
- **Python Environment**: Use the `scholarbot` conda/mamba environment
- **Package Installation**:
  - Prefer `mamba` for package installation (faster than conda)
  - Fallback to `pip` if package not available in mamba/conda
  - Example:
    ```bash
    conda activate scholarbot
    mamba install package_name  # Try mamba first
    pip install package_name     # Fallback to pip
    ```

## Development Workflow
- Format code with [`black`](https://black.readthedocs.io/en/stable/). Run:
  ```bash
  black .
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

## OpenAlex Backend

This project supports fetching publications via the OpenAlex API in addition to Google Scholar.

- Enable by setting in `settings.json`:
  - `"backend": "openalex"`
  - `"openalex_email"`: your contact email (required to join the "polite pool")
  - `"fetch_full_history"`: `true` to fetch all years, or `false` to use `from_year`
  - `"from_year"`: integer year when not fetching full history

### Polite Pool and Throttling
- All OpenAlex requests include the `mailto` param from `openalex_email` to join the polite pool.
- We use `per-page=200` and cursor pagination to minimize request count; rate limiting is rarely needed.

### Works Fetching (per author)
- Endpoint: `GET https://api.openalex.org/works`
- Filter: `author.id:A...` (accepts bare key or full URL)
- Paging: `per-page=200`, `cursor=*`, then iterate using `meta.next_cursor` until `null`.
- Sorting: `sort=cited_by_count:desc` (optional; helps with streamed UIs).
- Date window: use `from_publication_date:YYYY-01-01` when `from_year` is set. Do not use `publication_year:>=YYYY` (invalid).
- Field selection (kept minimal for bandwidth): `select=id,doi,display_name,publication_year,abstract_inverted_index,primary_location,cited_by_count,authorships,type`.

### Normalization Rules
- Title: from `display_name`.
- Abstract: reconstruct from `abstract_inverted_index`.
- Year: from `publication_year`.
- URL: prefer `primary_location.landing_page_url`, fallback to `primary_location.pdf_url`, else the work `id` (OpenAlex URL).
- Journal/source label: `primary_location.source.display_name` when available.
- Citations: `cited_by_count`.
- Authors (string): join `authorships[*].author.display_name`.
- Type filtering: keep only article-like items and preprints; allowed types include `journal-article`, `proceedings-article`, `book-chapter`, `report`, `book`, `preprint`, `posted-content`, and `article`. Filter out file-like titles (e.g., `.zip`, `.mat`, `.tar`).

### Database Model and Upserts
- Publications DB: `src/publications.db`.
- Schema adds optional columns when missing: `authors`, `journal`, `doi`, `source_id`.
- Primary key is `(author_id, title, source_id)` to keep distinct versions (e.g., preprint vs journal) under the same title.
- `source_id` is derived as: DOI if present, else URL if present, else title.
- Upserts never delete existing rows; the DB is the source of truth. Fetching only adds or updates.

### Author IDs and Resolution
- Authors can be added by Scholar ID, OpenAlex ID, or ORCID.
- When adding by ORCID, we resolve to OpenAlex using `GET /authors?filter=orcid:...` and store `openalex_id`.
- For Scholar backend, `scholarly` is only imported lazily during Scholar flows; OpenAlex-only setups do not require the `scholarly` package to be installed.

### Author Metrics (optional)
- You can query quick totals via `GET /authors/A...` with `select=id,display_name,works_count,cited_by_count,summary_stats,works_api_url`.
- We compute totals (sum of citations) and h-index locally from DB; the OpenAlex `summary_stats.h_index` can be used for comparison.

### Troubleshooting
- 403 "Invalid query parameters": remove unsupported fields from `select` (e.g., `host_venue` is not allowed in select).
- 400 "publication_year must be a number": do not use comparators in `publication_year`; use `from_publication_date:YYYY-01-01` instead.
- 0 results after a hard reset: run a cache refresh for one or more authors to repopulate the DB.

### Example cURL (A5087337335)
```bash
# Author summary
curl "https://api.openalex.org/authors/A5087337335?select=id,display_name,works_count,cited_by_count,works_api_url&mailto=YOUR_EMAIL"

# Works baseline (first page, no cursor)
curl "https://api.openalex.org/works?filter=author.id:A5087337335&per-page=25&mailto=YOUR_EMAIL"

# Works with cursor paging
curl "https://api.openalex.org/works?filter=author.id:A5087337335&per-page=200&cursor=*&mailto=YOUR_EMAIL"

# Since 2016
curl "https://api.openalex.org/works?filter=author.id:A5087337335,from_publication_date:2016-01-01&per-page=200&cursor=*&mailto=YOUR_EMAIL"
```

### Relevant Code
- OpenAlex client, polite paging, normalization, and upsert logic: `src/openalex/client.py`
- Backend facade switching between Scholar and OpenAlex: `fetch_backend.py`
- API DB dependencies and schema migration to composite PK: `src/api/deps.py`

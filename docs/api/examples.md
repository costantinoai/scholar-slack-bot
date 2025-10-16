# API Usage Examples

This guide provides practical examples for common use cases with the Scholar Slack Bot API.

## Table of Contents

- [curl Examples](#curl-examples)
- [Python Examples](#python-examples)
- [JavaScript Examples](#javascript-examples)
- [Common Use Cases](#common-use-cases)

---

## curl Examples

### Basic Operations

#### Check API Health
```bash
curl http://localhost:8000/api/v1/health
```

#### Get All Authors
```bash
curl http://localhost:8000/api/v1/authors
```

#### Add a New Author
```bash
curl -X POST http://localhost:8000/api/v1/authors \
  -H "Content-Type: application/json" \
  -d '{"scholar_id": "abc123xyz"}'
```

#### Get Author Details
```bash
curl http://localhost:8000/api/v1/authors/abc123xyz
```

#### Delete an Author
```bash
curl -X DELETE http://localhost:8000/api/v1/authors/abc123xyz
```

### Query Publications

#### Get Recent Publications (2024+)
```bash
curl "http://localhost:8000/api/v1/publications?min_year=2024&limit=20"
```

#### Get Highly Cited Publications
```bash
curl "http://localhost:8000/api/v1/publications?min_citations=50&limit=10"
```

#### Search Publications by Keywords
```bash
curl "http://localhost:8000/api/v1/publications?search=neural+networks"
```

#### Get Publications for Specific Author
```bash
curl "http://localhost:8000/api/v1/publications?author_id=abc123xyz"
```

#### Complex Query (recent, highly cited, keyword search)
```bash
curl "http://localhost:8000/api/v1/publications?min_year=2023&min_citations=20&search=deep+learning&limit=15"
```

### Plugin Management

#### List All Plugins
```bash
curl http://localhost:8000/api/v1/plugins
```

#### Get Plugin Details
```bash
curl http://localhost:8000/api/v1/plugins/slack
```

#### Configure Slack Plugin
```bash
curl -X PUT http://localhost:8000/api/v1/plugins/slack/config \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "api_token": "xoxb-your-slack-token",
      "default_channel": "#publications"
    }
  }'
```

#### Test Plugin Connection
```bash
curl -X POST http://localhost:8000/api/v1/plugins/slack/test
```

#### Send Test Notification
```bash
curl -X POST "http://localhost:8000/api/v1/plugins/slack/notify?message=Hello+from+API"
```

### Statistics

#### Get Overall Stats
```bash
curl http://localhost:8000/api/v1/stats
```

#### Get Publication Statistics
```bash
curl http://localhost:8000/api/v1/publications/stats
```

---

## Python Examples

### Basic Setup

```python
import requests

API_BASE_URL = "http://localhost:8000/api/v1"

# Optional: Add authentication
headers = {
    "X-API-Key": "your-api-key-here"  # Only if API_KEY is configured
}
```

### Managing Authors

```python
def add_author(scholar_id: str):
    """Add a new author to monitor."""
    response = requests.post(
        f"{API_BASE_URL}/authors",
        json={"scholar_id": scholar_id}
    )
    if response.status_code == 201:
        author = response.json()
        print(f"Added: {author['name']} ({author['id']})")
        return author
    else:
        print(f"Error: {response.json()}")
        return None

def list_all_authors():
    """Get all monitored authors."""
    response = requests.get(f"{API_BASE_URL}/authors")
    authors = response.json()
    for author in authors:
        print(f"{author['name']}: {author['publication_count']} publications")
    return authors

def delete_author(author_id: str):
    """Remove an author from monitoring."""
    response = requests.delete(f"{API_BASE_URL}/authors/{author_id}")
    if response.status_code == 204:
        print(f"Deleted author: {author_id}")
        return True
    else:
        print(f"Error: {response.json()}")
        return False

# Usage
add_author("abc123xyz")
authors = list_all_authors()
```

### Querying Publications

```python
def get_recent_publications(year: int = 2024, min_citations: int = 0):
    """Get recent highly-cited publications."""
    response = requests.get(
        f"{API_BASE_URL}/publications",
        params={
            "min_year": year,
            "min_citations": min_citations,
            "limit": 50
        }
    )
    publications = response.json()
    for pub in publications:
        print(f"{pub['title']} ({pub['year']}) - {pub['citations']} citations")
    return publications

def search_publications(query: str):
    """Search publications by keyword."""
    response = requests.get(
        f"{API_BASE_URL}/publications",
        params={"search": query, "limit": 20}
    )
    return response.json()

def get_author_publications(author_id: str):
    """Get all publications for a specific author."""
    response = requests.get(f"{API_BASE_URL}/authors/{author_id}/publications")
    return response.json()

# Usage
recent_pubs = get_recent_publications(year=2023, min_citations=20)
ml_papers = search_publications("machine learning")
author_pubs = get_author_publications("abc123xyz")
```

### Plugin Configuration

```python
def configure_slack_plugin(api_token: str, channel: str):
    """Configure the Slack plugin."""
    response = requests.put(
        f"{API_BASE_URL}/plugins/slack/config",
        json={
            "config": {
                "api_token": api_token,
                "default_channel": channel
            }
        }
    )
    result = response.json()
    print(f"Configuration: {result['message']}")
    return result

def test_plugin(plugin_name: str):
    """Test a plugin's connection."""
    response = requests.post(f"{API_BASE_URL}/plugins/{plugin_name}/test")
    result = response.json()
    print(f"Test result: {result['message']}")
    return result['success']

def send_test_notification(plugin_name: str, message: str):
    """Send a test notification via a plugin."""
    response = requests.post(
        f"{API_BASE_URL}/plugins/{plugin_name}/notify",
        params={"message": message}
    )
    return response.json()

# Usage
configure_slack_plugin("xoxb-your-token", "#publications")
if test_plugin("slack"):
    send_test_notification("slack", "Test from Python!")
```

### Complete Workflow Example

```python
import requests
from datetime import datetime

class ScholarBotClient:
    """Client for interacting with Scholar Slack Bot API."""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1", api_key: str = None):
        self.base_url = base_url
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key

    def health_check(self):
        """Check if API is healthy."""
        response = requests.get(f"{self.base_url}/health", headers=self.headers)
        return response.json()

    def add_authors(self, scholar_ids: list):
        """Add multiple authors."""
        results = []
        for scholar_id in scholar_ids:
            try:
                response = requests.post(
                    f"{self.base_url}/authors",
                    json={"scholar_id": scholar_id},
                    headers=self.headers
                )
                if response.status_code == 201:
                    results.append(response.json())
                else:
                    print(f"Failed to add {scholar_id}: {response.json()}")
            except Exception as e:
                print(f"Error adding {scholar_id}: {e}")
        return results

    def get_statistics(self):
        """Get overall statistics."""
        response = requests.get(f"{self.base_url}/stats", headers=self.headers)
        return response.json()

    def get_top_publications(self, min_citations: int = 50, year: int = None):
        """Get top publications by citations."""
        params = {"min_citations": min_citations, "limit": 100}
        if year:
            params["min_year"] = year

        response = requests.get(
            f"{self.base_url}/publications",
            params=params,
            headers=self.headers
        )
        return response.json()

# Usage
client = ScholarBotClient()

# Check health
health = client.health_check()
print(f"API Status: {health['status']}")

# Add authors
new_authors = client.add_authors([
    "abc123xyz",
    "def456uvw"
])
print(f"Added {len(new_authors)} authors")

# Get stats
stats = client.get_statistics()
print(f"Total: {stats['total_authors']} authors, {stats['total_publications']} publications")

# Get highly cited recent papers
top_pubs = client.get_top_publications(min_citations=30, year=2023)
print(f"Found {len(top_pubs)} highly-cited publications from 2023+")
```

---

## JavaScript Examples

### Using fetch (Browser/Node.js)

```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1';

// Add authentication header if needed
const headers = {
  'Content-Type': 'application/json',
  // 'X-API-Key': 'your-api-key-here'  // Uncomment if using API key
};

// Add a new author
async function addAuthor(scholarId) {
  const response = await fetch(`${API_BASE_URL}/authors`, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({ scholar_id: scholarId })
  });

  if (response.ok) {
    const author = await response.json();
    console.log(`Added: ${author.name} (${author.id})`);
    return author;
  } else {
    const error = await response.json();
    console.error('Error:', error);
    return null;
  }
}

// Get all authors
async function getAllAuthors() {
  const response = await fetch(`${API_BASE_URL}/authors`, { headers });
  const authors = await response.json();
  authors.forEach(author => {
    console.log(`${author.name}: ${author.publication_count} publications`);
  });
  return authors;
}

// Query publications
async function queryPublications(filters = {}) {
  const params = new URLSearchParams(filters);
  const response = await fetch(`${API_BASE_URL}/publications?${params}`, { headers });
  return await response.json();
}

// Usage
(async () => {
  await addAuthor('abc123xyz');
  const authors = await getAllAuthors();

  const recentPubs = await queryPublications({
    min_year: 2024,
    min_citations: 20,
    limit: 10
  });
  console.log('Recent publications:', recentPubs);
})();
```

### Using axios (Node.js)

```javascript
const axios = require('axios');

const client = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: {
    // 'X-API-Key': 'your-api-key-here'  // Uncomment if using API key
  }
});

// Add author
async function addAuthor(scholarId) {
  try {
    const response = await client.post('/authors', {
      scholar_id: scholarId
    });
    console.log('Added:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error:', error.response.data);
    return null;
  }
}

// Get statistics
async function getStats() {
  const response = await client.get('/stats');
  return response.data;
}

// Configure plugin
async function configurePlugin(pluginName, config) {
  const response = await client.put(`/plugins/${pluginName}/config`, {
    config: config
  });
  return response.data;
}

// Usage
(async () => {
  await addAuthor('abc123xyz');
  const stats = await getStats();
  console.log(`Total: ${stats.total_authors} authors`);

  await configurePlugin('slack', {
    api_token: 'xoxb-your-token',
    default_channel: '#publications'
  });
})();
```

---

## Common Use Cases

### 1. Bulk Import Authors

```python
# Import authors from a CSV file
import csv
import requests

API_BASE_URL = "http://localhost:8000/api/v1"

def bulk_import_authors(csv_file):
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            scholar_id = row['scholar_id']
            try:
                response = requests.post(
                    f"{API_BASE_URL}/authors",
                    json={"scholar_id": scholar_id}
                )
                if response.status_code == 201:
                    author = response.json()
                    print(f"✓ Added: {author['name']}")
                elif response.status_code == 409:
                    print(f"⊙ Already exists: {scholar_id}")
                else:
                    print(f"✗ Failed: {scholar_id}")
            except Exception as e:
                print(f"✗ Error with {scholar_id}: {e}")

bulk_import_authors('authors.csv')
```

### 2. Generate Publication Report

```python
import requests
from datetime import datetime

def generate_publication_report(year: int):
    """Generate a markdown report of publications from a specific year."""

    # Get publications
    response = requests.get(
        "http://localhost:8000/api/v1/publications",
        params={"year": year, "limit": 1000}
    )
    publications = response.json()

    # Sort by citations
    publications.sort(key=lambda p: p['citations'], reverse=True)

    # Generate report
    report = f"# Publications from {year}\n\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    report += f"Total: {len(publications)} publications\n\n"

    report += "## Top 10 Most Cited\n\n"
    for i, pub in enumerate(publications[:10], 1):
        report += f"{i}. **{pub['title']}** ({pub['citations']} citations)\n"
        report += f"   - Year: {pub['year']}\n"
        report += f"   - URL: {pub['url']}\n\n"

    with open(f'publications_{year}_report.md', 'w') as f:
        f.write(report)

    print(f"Report saved to publications_{year}_report.md")

generate_publication_report(2024)
```

### 3. Monitor for New Publications

```python
import requests
import time

def monitor_new_publications(check_interval: int = 3600):
    """Check for new publications periodically."""

    last_check = {}

    while True:
        authors = requests.get("http://localhost:8000/api/v1/authors").json()

        for author in authors:
            current_count = author['publication_count']
            previous_count = last_check.get(author['id'], 0)

            if current_count > previous_count:
                new_pubs = current_count - previous_count
                print(f"🔔 {author['name']} has {new_pubs} new publication(s)!")

            last_check[author['id']] = current_count

        print(f"✓ Checked at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(check_interval)  # Wait before next check

# Run every hour
monitor_new_publications(check_interval=3600)
```

### 4. Export Publications to CSV

```python
import requests
import csv

def export_publications_to_csv(filename: str = "publications.csv"):
    """Export all publications to a CSV file."""

    response = requests.get(
        "http://localhost:8000/api/v1/publications",
        params={"limit": 1000}
    )
    publications = response.json()

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['author_id', 'title', 'year', 'citations', 'url']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        for pub in publications:
            writer.writerow({
                'author_id': pub['author_id'],
                'title': pub['title'],
                'year': pub['year'],
                'citations': pub['citations'],
                'url': pub['url']
            })

    print(f"Exported {len(publications)} publications to {filename}")

export_publications_to_csv()
```

---

## Error Handling

Always handle errors gracefully:

```python
import requests

def safe_api_call(url, method='GET', **kwargs):
    """Make an API call with error handling."""
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()  # Raise exception for 4xx/5xx
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e.response.status_code}")
        print(f"Details: {e.response.json()}")
        return None
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API server")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

# Usage
result = safe_api_call("http://localhost:8000/api/v1/authors")
if result:
    print(f"Retrieved {len(result)} authors")
```

---

## Next Steps

- Explore the [Complete API Reference](reference.md) for all available endpoints
- Check out the [Interactive Documentation](http://localhost:8000/docs) for live testing
- Review the main [README](README.md) for setup instructions

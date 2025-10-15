# Golden Tests for Scholar Publication Bot

## Overview

This project has **two types** of golden tests to ensure core functionality remains intact during refactoring:

1. **Fast Golden Tests** (mocked) - Run on every commit
2. **Real Golden Test** (actual APIs) - Run before releases/major changes

Both should **ALWAYS PASS** to ensure nothing is broken.

---

## 1. Fast Golden Tests (Mocked) 🏃

**File**: `tests/test_golden_simple.py`

### Purpose
Quick validation tests that run in milliseconds using mocked external APIs. Safe to run on every commit.

### Tests Included

#### `test_golden_workflow_complete`
Validates complete workflow with mocked Scholar/Slack APIs:
- Load authors from database
- Fetch publications (mocked)
- Update database
- Format messages
- Send notifications (mocked)

#### `test_golden_workflow_no_new_publications`
Ensures graceful handling of empty results

#### `test_golden_database_operations`
Verifies database read/write operations

#### `test_golden_message_formatting`
Validates Slack message formatting

### Running Fast Golden Tests

```bash
# Run all fast golden tests
pytest tests/test_golden_simple.py -v

# Expected output: "4 passed in 0.16s"
```

**When to run**: On every commit, before every push, during development

---

## 2. Real Golden Test (Actual APIs) 🌐

**File**: `tests/test_golden_real.py`

### Purpose
**THE MOST IMPORTANT TEST** - Makes actual API calls to ensure the complete workflow works in reality, not just with mocks. This is the TRUE golden test.

### What It Does

1. **Fetches REAL data** from Google Scholar (1 publication, 1 author)
2. **Saves to REAL database** (SQLite)
3. **Sends REAL Slack message** (with `[TEST]` tag)
4. **Validates end-to-end** workflow

### Prerequisites

The test requires valid credentials:

**Option 1: Environment Variables**
```bash
export RUN_GOLDEN_TEST=1                    # Enable the test
export SLACK_API_TOKEN=xoxb-your-token      # Your Slack bot token
export SLACK_TEST_CHANNEL=test-channel      # (Optional) specific channel
```

**Option 2: Config File**
Configure `./src/slack.config`:
```ini
[slack]
api_token = xoxb-your-slack-token
channel_name = your-test-channel
```

### Running Real Golden Test

```bash
# Set environment variable to enable
export RUN_GOLDEN_TEST=1

# Run the real golden test
pytest tests/test_golden_real.py::test_golden_real_workflow_complete -v -s

# Or run directly
python tests/test_golden_real.py
```

### Expected Output

```
============================================================
🧪 GOLDEN TEST - REAL API CALLS
============================================================
📚 Fetching from: Google Scholar
👤 Test Author: Albert Einstein (qc6CJjYAAAAJ)
💬 Slack Channel: your-channel
⏰ Timestamp: 2024-10-15T14:30:00
============================================================

📡 Step 1: Loading authors from database...
   ✅ Loaded: Albert Einstein

📡 Step 2: Fetching publications from Google Scholar...
   ⚠️  This makes a REAL API call to scholar.google.com
   ⏳ Please wait...
   ✅ Fetched 1 publications from 2024

📡 Step 3: Checking database persistence...
   ✅ Database contains 1 publications for test author

📡 Step 4: Formatting Slack message...
   ✅ Formatted 2 message(s)

📡 Step 5: Sending to Slack...
   ⚠️  This makes a REAL API call to Slack
   📤 Sending to: your-channel
   ✅ Message 1/2 sent successfully
   ✅ Message 2/2 sent successfully
   ✅ Successfully sent 2 message(s) to Slack

============================================================
✅ GOLDEN TEST PASSED - Complete workflow executed successfully!
============================================================
Summary:
  • Authors loaded: 1
  • Publications fetched: 1
  • Messages sent: 2
  • Slack channel: your-channel
============================================================
```

### What Gets Sent to Slack

The test sends a message with clear `[TEST]` markers:

```
╔═══════════════════════════════════════════════╗
║  🧪 GOLDEN TEST - AUTOMATED TEST MESSAGE 🧪  ║
║  This is an automated test of the bot        ║
║  Time: 2024-10-15 14:30:00                   ║
╚═══════════════════════════════════════════════╝

[Your actual formatted publication messages]

╔═══════════════════════════════════╗
║  ✅ GOLDEN TEST COMPLETED  ✅     ║
╚═══════════════════════════════════╝
```

### When to Run

**MUST run before**:
- Creating a release
- Merging to main branch
- Major refactoring (before and after)
- Deploying to production

**Optional but recommended**:
- After fixing API-related bugs
- After changing Scholar/Slack integration
- Weekly/monthly sanity check

### Why This Test Matters

Mocked tests can pass while real integration is broken. This test ensures:

✅ **Google Scholar API** actually works
✅ **Slack API** actually works
✅ **Network connectivity** is working
✅ **API credentials** are valid
✅ **Rate limiting** isn't exceeded
✅ **Data formatting** is correct for real APIs
✅ **Complete workflow** works end-to-end

### Rate Limiting

This test makes **real API calls**, so:
- Don't run it in CI on every commit
- Don't run it more than a few times per hour
- Google Scholar may rate-limit if abused
- Use it as a **manual gate before releases**

---

## Test-Driven Refactoring Workflow

### During Development (Fast Tests)

```bash
# 1. Before starting
pytest tests/test_golden_simple.py -v
# ✅ 4 passed in 0.16s

# 2. Make changes...

# 3. After each significant change
pytest tests/test_golden_simple.py -v
# ✅ 4 passed in 0.16s

# 4. Before committing
pytest -v
# ✅ 38 passed in 0.36s

git commit -m "refactor: [description]"
```

### Before Release (Real Test)

```bash
# 1. Set up credentials
export RUN_GOLDEN_TEST=1
export SLACK_API_TOKEN=xoxb-your-token

# 2. Run fast tests
pytest tests/test_golden_simple.py -v
# ✅ 4 passed

# 3. Run REAL golden test
pytest tests/test_golden_real.py::test_golden_real_workflow_complete -v -s

# ✅ Check Slack - you should see the test message

# 4. If all pass - safe to release!
git tag v1.0.0
git push --tags
```

---

## Complete Test Suite

### Current Status

```
38 total tests (all passing)
├── 4 fast golden tests (mocked)
├── 2 real golden tests (actual APIs)
├── 8 fetch_scholar tests
├── 15 slack_bot tests
├── 5 helper_funcs tests
└── 3 main tests
```

### Coverage by Module

| Module | Unit Tests | Golden (Fast) | Golden (Real) |
|--------|-----------|---------------|---------------|
| `fetch_scholar.py` | ✅ 8 tests | ✅ Mocked | ✅ Real API |
| `slack_bot.py` | ✅ 15 tests | ✅ Mocked | ✅ Real API |
| `helper_funcs.py` | ✅ 5 tests | ✅ Covered | ✅ Covered |
| `main.py` | ✅ 3 tests | ⚠️ Partial | ✅ Complete E2E |
| **End-to-End** | — | **✅ Fast** | **✅ Real** |

---

## Quick Reference

### Run Fast Tests (Always)
```bash
pytest tests/test_golden_simple.py -v
```

### Run Real Test (Before Release)
```bash
export RUN_GOLDEN_TEST=1
pytest tests/test_golden_real.py -v -s
```

### Run All Tests
```bash
pytest -v
```

### Run with Coverage
```bash
pytest --cov=. --cov-report=term-missing tests/test_golden_simple.py
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test

on: [push, pull_request]

jobs:
  # Fast tests run on every commit
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run fast golden tests
        run: pytest tests/test_golden_simple.py -v
      - name: Run all tests
        run: pytest -v

  # Real golden test only runs on release
  golden-real:
    runs-on: ubuntu-latest
    if: github.event_name == 'release'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run REAL golden test
        env:
          RUN_GOLDEN_TEST: 1
          SLACK_API_TOKEN: ${{ secrets.SLACK_API_TOKEN }}
          SLACK_TEST_CHANNEL: ${{ secrets.SLACK_TEST_CHANNEL }}
        run: pytest tests/test_golden_real.py -v -s
```

---

## Troubleshooting

### Fast Tests Fail
- You broke core functionality
- Fix your code, don't update tests (unless intentional behavior change)
- Use `pytest -vv --pdb` to debug

### Real Test Skipped
```bash
# Check if enabled
echo $RUN_GOLDEN_TEST  # Should be "1"

# Check credentials
echo $SLACK_API_TOKEN  # Should be "xoxb-..."
```

### Real Test Fails - "No Slack token"
```bash
export SLACK_API_TOKEN=xoxb-your-token-here
# Or configure ./src/slack.config
```

### Real Test Fails - "Rate limited"
- Google Scholar is rate-limiting
- Wait 10-15 minutes and try again
- Don't run this test too frequently

### Real Test Hangs
- Network issue or API timeout
- Check internet connection
- Try again in a few minutes

---

## Best Practices

### ✅ DO
- Run fast tests on every commit
- Run real test before every release
- Keep test author (Einstein) stable and public
- Use clear `[TEST]` tags in messages
- Document any test failures

### ❌ DON'T
- Don't run real test in CI on every commit
- Don't run real test more than a few times per hour
- Don't skip real test before major releases
- Don't update tests just to make them pass
- Don't commit with failing fast tests

---

## Summary

| Test Type | Speed | API Calls | When to Run | Purpose |
|-----------|-------|-----------|-------------|---------|
| **Fast Golden** | 0.16s | ❌ Mocked | Every commit | Catch regressions quickly |
| **Real Golden** | ~10s | ✅ Real | Before releases | Validate actual integration |

**Both types are important:**
- Fast tests give you **confidence during development**
- Real test gives you **confidence before deployment**

---

**Last Updated**: 2024-10-15
**Status**: ✅ All Tests Passing (38 fast + 2 real)
**Next Steps**: Ready for safe refactoring!

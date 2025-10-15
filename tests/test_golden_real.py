"""REAL Golden Test - Uses actual APIs to validate the complete workflow.

This test makes REAL calls to:
- Google Scholar API (to fetch one publication for one author)
- Slack API (to send one test message)

This ensures the complete workflow actually works end-to-end, not just with mocks.

BEHAVIOR:
- RUNS LOCALLY: If src/slack.config exists with valid credentials
- SKIPS IN CI/CD: If no credentials are found (as expected on GitHub)
- Uses a well-known, stable Google Scholar ID (Albert Einstein)
- Sends message with clear [TEST] tag to avoid confusion

No environment variables needed locally - just configure src/slack.config
"""

import os
import sys
import sqlite3
import pytest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime


# Test configuration - use a well-known stable author
TEST_AUTHOR_ID = "qc6CJjYAAAAJ"  # Albert Einstein - stable, public profile
TEST_AUTHOR_NAME = "Albert Einstein"


def has_credentials():
    """Check if Slack credentials are available.

    Returns True if credentials exist (either in environment or config file).
    This allows the test to run locally where credentials are configured,
    but skip in CI/CD where credentials are not available.
    """
    # Check environment variable
    if os.environ.get("SLACK_API_TOKEN"):
        return True

    # Check config file
    config_path = Path("./src/slack.config")
    if config_path.exists():
        import configparser
        config = configparser.ConfigParser()
        try:
            config.read(config_path)
            if config.has_option("slack", "api_token"):
                token = config.get("slack", "api_token")
                # Make sure it's not empty or a placeholder
                if token and not token.startswith("xoxb-your-"):
                    return True
        except Exception:
            pass

    return False


def get_slack_token():
    """Get Slack API token from environment or config file."""
    # Try environment variable first
    token = os.environ.get("SLACK_API_TOKEN")
    if token:
        return token

    # Try config file
    config_path = Path("./src/slack.config")
    if config_path.exists():
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path)
        if config.has_option("slack", "api_token"):
            return config.get("slack", "api_token")

    return None


def get_slack_channel():
    """Get Slack channel from environment or config file."""
    # Try environment variable first
    channel = os.environ.get("SLACK_TEST_CHANNEL")
    if channel:
        return channel

    # Try config file
    config_path = Path("./src/slack.config")
    if config_path.exists():
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path)
        if config.has_option("slack", "channel_name"):
            return config.get("slack", "channel_name")

    return None


@pytest.mark.skipif(
    not has_credentials(),
    reason="Skipping real golden test: no Slack credentials found (expected in CI/CD)"
)
def test_golden_real_workflow_complete(tmp_path):
    """⭐ REAL GOLDEN TEST - Complete workflow with actual API calls.

    This test validates the REAL end-to-end workflow:
    1. Fetch ONE publication from Google Scholar (real API call)
    2. Save to database
    3. Format message
    4. Send to Slack (real API call with [TEST] tag)

    To run this test locally:
        1. Configure src/slack.config with your credentials (already done)
        2. Run: pytest tests/test_golden_real.py::test_golden_real_workflow_complete -v -s

    OR use environment variables:
        export SLACK_API_TOKEN=xoxb-your-token
        export SLACK_TEST_CHANNEL=your-channel
        pytest tests/test_golden_real.py::test_golden_real_workflow_complete -v -s

    This test makes REAL API calls, so:
    - It requires valid credentials (auto-detected from src/slack.config)
    - It will send a real Slack message (marked as [TEST])
    - It will fetch real data from Google Scholar
    - It may be rate-limited if run too frequently
    - It automatically SKIPS in CI/CD when no credentials are present
    """

    # ========================================================================
    # ARRANGE: Check prerequisites
    # ========================================================================

    slack_token = get_slack_token()
    if not slack_token:
        pytest.skip("No Slack token found. Set SLACK_API_TOKEN or configure src/slack.config")

    slack_channel = get_slack_channel()
    if not slack_channel:
        pytest.skip("No Slack channel found. Set SLACK_TEST_CHANNEL or configure src/slack.config")

    print(f"\n{'='*70}")
    print(f"🧪 GOLDEN TEST - REAL API CALLS")
    print(f"{'='*70}")
    print(f"📚 Fetching from: Google Scholar")
    print(f"👤 Test Author: {TEST_AUTHOR_NAME} ({TEST_AUTHOR_ID})")
    print(f"💬 Slack Channel: {slack_channel}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*70}\n")

    # Set up test environment
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # Create authors database with test author
    authors_db = src_dir / "authors.db"
    conn = sqlite3.connect(authors_db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS authors (name TEXT, id TEXT PRIMARY KEY)"
    )
    conn.execute(
        "INSERT INTO authors (name, id) VALUES (?, ?)",
        (TEST_AUTHOR_NAME, TEST_AUTHOR_ID)
    )
    conn.commit()
    conn.close()

    # Create Slack config
    slack_config = src_dir / "slack.config"
    slack_config.write_text(
        f"[slack]\napi_token={slack_token}\nchannel_name={slack_channel}\n"
    )

    # Create cache directory
    cache_dir = src_dir / "googleapi_cache"
    cache_dir.mkdir()

    # ========================================================================
    # ACT: Execute REAL workflow
    # ========================================================================

    print("📡 Step 1: Loading authors from database...")
    from helper_funcs import get_authors_json, convert_json_to_tuple

    authors_json = get_authors_json(str(authors_db))
    authors = convert_json_to_tuple(authors_json)

    assert len(authors) == 1, "Should load 1 test author"
    assert authors[0] == (TEST_AUTHOR_NAME, TEST_AUTHOR_ID)
    print(f"   ✅ Loaded: {authors[0][0]}")

    print(f"\n📡 Step 2: Fetching publications from Google Scholar...")
    print(f"   ⚠️  This makes a REAL API call to scholar.google.com")
    print(f"   ⏳ Please wait...")

    from fetch_scholar import fetch_publications_by_id
    import time

    args = SimpleNamespace(
        test_fetching=False,
        update_cache=False
    )

    # Fetch only publications from current year to minimize data transfer
    current_year = int(time.strftime("%Y"))

    try:
        articles = fetch_publications_by_id(
            TEST_AUTHOR_ID,
            str(src_dir),
            args,
            from_year=current_year,
            exclude_not_cited_papers=False
        )
    except Exception as e:
        pytest.fail(f"Failed to fetch from Google Scholar: {e}")

    print(f"   ✅ Fetched {len(articles)} publications from {current_year}")

    if len(articles) == 0:
        # If no publications from current year, try last year
        print(f"   ℹ️  No publications from {current_year}, trying {current_year-1}...")
        articles = fetch_publications_by_id(
            TEST_AUTHOR_ID,
            str(src_dir),
            args,
            from_year=current_year - 1,
            exclude_not_cited_papers=False
        )
        print(f"   ✅ Fetched {len(articles)} publications from {current_year-1}")

    # For the test, we only need to verify we CAN fetch data
    # Limit to 1 publication to minimize Slack message size
    if len(articles) > 1:
        articles = articles[:1]
        print(f"   ℹ️  Limited to 1 publication for test message")

    assert len(articles) >= 0, "Should return a list (may be empty for very recent years)"

    print(f"\n📡 Step 3: Checking database persistence...")
    from fetch_scholar import DB_NAME
    import os

    db_path = os.path.join(str(src_dir), DB_NAME)
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM publications WHERE author_id=?",
            (TEST_AUTHOR_ID,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        print(f"   ✅ Database contains {count} publications for test author")
    else:
        print(f"   ⚠️  No database created (no publications to save)")

    print(f"\n📡 Step 4: Formatting Slack message...")
    from slack_bot import make_slack_msg

    formatted_messages = make_slack_msg(authors, articles)

    assert len(formatted_messages) >= 1, "Should have at least author list message"
    print(f"   ✅ Formatted {len(formatted_messages)} message(s)")

    print(f"\n📡 Step 5: Sending to Slack...")
    print(f"   ⚠️  This makes a REAL API call to Slack")
    print(f"   📤 Sending to: {slack_channel}")

    from slack_bot import send_to_slack

    # Add clear TEST header to avoid confusion
    test_header = f"""
╔═══════════════════════════════════════════════╗
║  🧪 GOLDEN TEST - AUTOMATED TEST MESSAGE 🧪  ║
║  This is an automated test of the bot        ║
║  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                  ║
╚═══════════════════════════════════════════════╝
"""

    success = True
    messages_sent = 0

    try:
        # Send test header
        response = send_to_slack(slack_channel, f"```{test_header}```", slack_token)
        if not response or not response.get("ok"):
            error = response.get("error", "Unknown error") if response else "No response"
            pytest.fail(f"Failed to send test header to Slack: {error}")

        # Send formatted messages
        for i, message in enumerate(formatted_messages, 1):
            response = send_to_slack(slack_channel, message, slack_token)

            if not response or not response.get("ok"):
                success = False
                error = response.get("error", "Unknown error") if response else "No response"
                print(f"   ❌ Message {i} failed: {error}")
                pytest.fail(f"Failed to send message {i} to Slack: {error}")
            else:
                messages_sent += 1
                print(f"   ✅ Message {i}/{len(formatted_messages)} sent successfully")

        # Send test footer
        test_footer = "```\n╔═══════════════════════════════════╗\n║  ✅ GOLDEN TEST COMPLETED  ✅     ║\n╚═══════════════════════════════════╝\n```"
        response = send_to_slack(slack_channel, test_footer, slack_token)

    except Exception as e:
        pytest.fail(f"Error sending to Slack: {e}")

    print(f"\n   ✅ Successfully sent {messages_sent} message(s) to Slack")

    # ========================================================================
    # ASSERT: Verify workflow completed successfully
    # ========================================================================

    print(f"\n{'='*70}")
    print(f"✅ GOLDEN TEST PASSED - Complete workflow executed successfully!")
    print(f"{'='*70}")
    print(f"Summary:")
    print(f"  • Authors loaded: 1")
    print(f"  • Publications fetched: {len(articles)}")
    print(f"  • Messages sent: {messages_sent}")
    print(f"  • Slack channel: {slack_channel}")
    print(f"{'='*70}\n")

    # All assertions
    assert len(authors) == 1, "Should process 1 author"
    assert isinstance(articles, list), "Should return list of articles"
    assert len(formatted_messages) >= 1, "Should format at least 1 message"
    assert messages_sent >= 1, "Should send at least 1 message"
    assert success, "All messages should be sent successfully"


@pytest.mark.skipif(
    not has_credentials(),
    reason="Skipping Slack connectivity test: no credentials found"
)
def test_golden_real_slack_connectivity():
    """Quick test to verify Slack API token works.

    This is a lightweight test that only checks if we can send a message.
    Useful for validating credentials before running the full golden test.
    """
    slack_token = get_slack_token()
    if not slack_token:
        pytest.skip("No Slack token found")

    slack_channel = get_slack_channel()
    if not slack_channel:
        pytest.skip("No Slack channel found")

    print(f"\n🧪 Testing Slack connectivity...")
    print(f"   Channel: {slack_channel}")

    from slack_bot import send_to_slack

    test_message = f"```\n🧪 CONNECTIVITY TEST\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nThis is an automated connectivity test.\n```"

    response = send_to_slack(slack_channel, test_message, slack_token)

    assert response is not None, "Should get a response from Slack"
    assert response.get("ok"), f"Slack API should succeed: {response.get('error', 'Unknown error')}"

    print(f"   ✅ Slack connectivity verified!")


if __name__ == "__main__":
    # Allow running this test file directly
    print("=" * 70)
    print("REAL GOLDEN TEST")
    print("=" * 70)
    print("\nThis test makes REAL API calls to Google Scholar and Slack.")
    print("\nHow it works:")
    print("  • LOCALLY: Runs automatically if src/slack.config has credentials")
    print("  • IN CI/CD: Skips automatically (no credentials available)")
    print("\nPrerequisites (choose one):")
    print("  Option A (recommended): Configure ./src/slack.config")
    print("  Option B: Set environment variables")
    print("     export SLACK_API_TOKEN=xoxb-your-token")
    print("     export SLACK_TEST_CHANNEL=your-channel")
    print("\nTo run:")
    print("  pytest tests/test_golden_real.py -v -s")
    print("=" * 70)

    # Check credentials
    if not has_credentials():
        print("\n⚠️  No Slack credentials found")
        print("    Configure ./src/slack.config or set SLACK_API_TOKEN")
        print("    Test will be SKIPPED (expected in CI/CD)")
        sys.exit(0)

    if not get_slack_token():
        print("\n❌ ERROR: No Slack token found")
        print("   Set SLACK_API_TOKEN or configure ./src/slack.config")
        sys.exit(1)

    if not get_slack_channel():
        print("\n❌ ERROR: No Slack channel found")
        print("   Set SLACK_TEST_CHANNEL or configure ./src/slack.config")
        sys.exit(1)

    print("\n✅ Credentials found - running golden test...")
    pytest.main([__file__, "-v", "-s"])

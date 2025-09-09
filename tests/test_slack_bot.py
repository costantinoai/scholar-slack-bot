from unittest.mock import Mock, patch

from slack_bot import make_slack_msg, get_channel_id_by_name, send_to_slack


def test_make_slack_msg_handles_duplicates_and_formats():
    authors = [("Alice", "A1"), ("Bob", "B1")]
    articles = [
        {
            "title": "Title1",
            "authors": "Alice",
            "abstract": "A",
            "year": "2023",
            "num_citations": 2,
            "journal": "Journal1",
            "pub_url": "url1",
        },
        {
            "title": "Title1",
            "authors": "Alice",
            "abstract": "A",
            "year": "2023",
            "num_citations": 2,
            "journal": "Journal1",
            "pub_url": "url1",
        },
    ]

    messages = make_slack_msg(authors, articles)

    assert messages[0].startswith("List of monitored authors")
    assert messages[1] == "List of publications since my last check:\n"
    assert len(messages) == 3  # authors message + header + 1 unique article message
    assert "Title1" in messages[2]


def test_make_slack_msg_no_articles():
    authors = [("Alice", "A1")]

    messages = make_slack_msg(authors, [])

    assert messages[0].startswith("List of monitored authors")
    assert messages[1] == "No new publications since my last check."


@patch("slack_bot.requests.get")
def test_get_channel_id_by_name_found(mock_get):
    mock_resp = {
        "ok": True,
        "channels": [
            {"name": "general", "id": "C123"},
            {"name": "random", "id": "C456"},
        ],
        "response_metadata": {},
    }
    mock_get.return_value = Mock()
    mock_get.return_value.json.return_value = mock_resp

    channel_id = get_channel_id_by_name("general", "token")

    assert channel_id == "C123"
    mock_get.assert_called_once()


@patch("slack_bot.requests.get")
def test_get_channel_id_by_name_not_found(mock_get):
    mock_resp = {"ok": True, "channels": [], "response_metadata": {}}
    mock_get.return_value = Mock()
    mock_get.return_value.json.return_value = mock_resp

    channel_id = get_channel_id_by_name("missing", "token")

    assert channel_id is None


@patch("slack_bot._send_message_to_channel")
@patch("slack_bot.get_channel_id_by_name")
def test_send_to_slack_channel(mock_get_channel, mock_send):
    mock_get_channel.return_value = "C123"
    mock_send.return_value = {"ok": True}

    resp = send_to_slack("general", "hi", "token")

    assert resp == {"ok": True}
    mock_send.assert_called_once_with("C123", "hi", "token")


@patch("slack_bot._send_message_to_channel")
@patch("slack_bot.open_im_channel")
@patch("slack_bot.get_user_id_by_name")
@patch("slack_bot.get_channel_id_by_name")
def test_send_to_slack_user(mock_get_channel, mock_get_user, mock_open_im, mock_send):
    mock_get_channel.return_value = None
    mock_get_user.return_value = "U1"
    mock_open_im.return_value = "D1"
    mock_send.return_value = {"ok": True}

    resp = send_to_slack("alice", "hi", "token")

    assert resp == {"ok": True}
    mock_open_im.assert_called_once_with("U1", "token")
    mock_send.assert_called_once_with("D1", "hi", "token")


@patch("slack_bot._send_message_to_channel")
@patch("slack_bot.get_user_id_by_name")
@patch("slack_bot.get_channel_id_by_name")
def test_send_to_slack_invalid(mock_get_channel, mock_get_user, mock_send):
    mock_get_channel.return_value = None
    mock_get_user.return_value = None

    resp = send_to_slack("unknown", "hi", "token")

    assert resp is None
    mock_send.assert_not_called()

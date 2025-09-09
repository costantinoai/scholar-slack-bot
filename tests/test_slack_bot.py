from unittest.mock import Mock, patch

from slack_bot import (
    _send_message_to_channel,
    format_authors_message,
    format_pub_message,
    get_channel_id_by_name,
    get_slack_config,
    get_user_id_by_name,
    make_slack_msg,
    open_im_channel,
    send_test_msg,
    send_to_slack,
)


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


def test_format_authors_message_sorts_and_formats():
    authors = [("Bob", "B"), ("Alice", "A")]
    message = format_authors_message(authors)
    assert message.index("Alice") < message.index("Bob")
    assert message.startswith("List of monitored authors:")


def test_format_pub_message_handles_many_authors():
    pub = {
        "title": "T",
        "authors": "A1,A2,A3,A4,A5",
        "abstract": "Abs",
        "year": "2023",
        "journal": "J",
        "pub_url": "url",
    }
    msg = format_pub_message(pub)
    assert "Authors: A1, [+3], A5" in msg
    assert msg.startswith("-" * 50)


def test_format_pub_message_handles_few_authors():
    pub = {
        "title": "T",
        "authors": "A1,A2",
        "abstract": "Abs",
        "year": "2023",
        "journal": "J",
        "pub_url": "url",
    }
    msg = format_pub_message(pub)
    assert "Authors: A1,A2" in msg


def test_get_slack_config_reads_file(tmp_path):
    cfg = tmp_path / "slack.config"
    cfg.write_text("[slack]\napi_token=tok\nchannel_name=chan\n")
    conf = get_slack_config(str(cfg))
    assert conf == {"api_token": "tok", "channel_name": "chan"}


@patch("slack_bot.requests.get")
def test_get_user_id_by_name_found(mock_get):
    mock_resp = {
        "ok": True,
        "members": [{"name": "alice", "real_name": "Alice", "id": "U1"}],
        "response_metadata": {},
    }
    mock_get.return_value = Mock()
    mock_get.return_value.json.return_value = mock_resp
    assert get_user_id_by_name("alice", "token") == "U1"


@patch("slack_bot.requests.get")
def test_get_user_id_by_name_not_found(mock_get):
    mock_resp = {"ok": True, "members": [], "response_metadata": {}}
    mock_get.return_value = Mock()
    mock_get.return_value.json.return_value = mock_resp
    assert get_user_id_by_name("bob", "token") is None


@patch("slack_bot.requests.post")
def test_open_im_channel_success(mock_post):
    mock_post.return_value = Mock()
    mock_post.return_value.json.return_value = {"ok": True, "channel": {"id": "D1"}}
    assert open_im_channel("U1", "token") == "D1"


@patch("slack_bot.requests.post")
def test_open_im_channel_failure(mock_post):
    mock_post.return_value = Mock()
    mock_post.return_value.json.return_value = {"ok": False, "error": "bad"}
    assert open_im_channel("U1", "token") is None


@patch("slack_bot.requests.post")
def test_send_message_to_channel_success(mock_post):
    mock_post.return_value = Mock()
    mock_post.return_value.json.return_value = {"ok": True}
    resp = _send_message_to_channel("C1", "hi", "token")
    assert resp == {"ok": True}
    mock_post.assert_called_once()


@patch("slack_bot.requests.post")
def test_send_message_to_channel_failure(mock_post):
    mock_post.return_value = Mock()
    mock_post.return_value.json.return_value = {"ok": False, "error": "bad"}
    resp = _send_message_to_channel("C1", "hi", "token")
    assert resp == {"ok": False, "error": "bad"}


@patch("slack_bot.send_to_slack")
def test_send_test_msg_formats_message(mock_send):
    send_test_msg("token", "chan")
    unformatted = "This is a test message"
    width = len(unformatted) + 2
    top_bottom = "#" * width
    formatted = f"```\n{top_bottom}\n#{unformatted}#\n{top_bottom}```"
    mock_send.assert_called_once_with("chan", formatted, "token")

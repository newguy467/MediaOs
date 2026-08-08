
from unittest.mock import patch, MagicMock
from app.services.hooks import notify_grab

def test_notify_grab_no_config_noop():
    # Should not raise when no webhooks configured
    notify_grab("Test Movie 2024", "YTS")

def test_notify_grab_discord_called():
    with patch("app.services.hooks.settings") as st:
        st.discord_webhook_url = "https://discord.test/webhook"
        st.notification_discord_webhook = None
        st.telegram_bot_token = None
        st.telegram_chat_id = None
        with patch("httpx.post") as post:
            post.return_value = MagicMock()
            notify_grab("Episode S01E01", "1337x")
            assert post.called
            args, kwargs = post.call_args
            assert "discord.test" in args[0]
            assert "grabbed" in kwargs["json"]["content"].lower() or "Episode" in kwargs["json"]["content"]

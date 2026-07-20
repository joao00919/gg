from functions.emoji import emoji


def test_requested_loading_animation_is_global():
    assert str(emoji.loading) == "<a:1389945080172904539:1527386782776164392>"


def test_cloud_emoji_aliases_are_available():
    assert hasattr(emoji, "members")
    assert hasattr(emoji, "user")
    assert hasattr(emoji, "role")


def test_cloud_bridge_uses_compatible_manager():
    from modules.cloud.update_api import get_websocket_manager
    manager = get_websocket_manager()
    for name in ("set_bot", "set_callbacks", "start", "stop", "check_auth_count"):
        assert hasattr(manager, name)

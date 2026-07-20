from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_close_ticket_dm_has_transcript_feedback_and_online_button():
    source = (ROOT / "modules/tickets/functions/setup_functions/close_ticket.py").read_text(encoding="utf-8")
    assert 'title="Ticket fechado"' in source
    assert 'label="Deixe um feedback"' in source
    assert 'custom_id=f"ticket_review_dm:{channel.id}"' in source
    assert 'label="Ver Transcript Online"' in source
    assert 'filename=f"transcript-{channel.name}.html"' in source


def test_assume_ticket_dm_has_support_button():
    source = (ROOT / "modules/tickets/functions/setup_functions/assume_ticket.py").read_text(encoding="utf-8")
    assert 'title="Ticket assumido"' in source
    assert 'label="Ir até o suporte"' in source
    assert 'url=channel.jump_url' in source


def test_dm_feedback_listener_is_registered():
    cog = (ROOT / "modules/tickets/functions/cog.py").read_text(encoding="utf-8")
    review = (ROOT / "modules/tickets/functions/setup_functions/review.py").read_text(encoding="utf-8")
    assert 'custom_id.startswith("ticket_review_dm:")' in cog
    assert 'async def review_from_dm' in review

from __future__ import annotations

from datetime import date

from app.renderers.character_renderer import build_character_list_keyboard, build_character_list_text
from app.renderers.episode_renderer import build_episode_list_keyboard, build_episode_list_text
from app.renderers.staff_renderer import build_staff_list_keyboard, build_staff_list_text
from app.services.character_service import CharacterDisplay
from app.services.episode_service import EpisodeDisplay
from app.services.staff_service import StaffDisplay


def test_episode_list_text_includes_title_and_air_date() -> None:
    episodes = [
        EpisodeDisplay(number=1, title="Romance Dawn", air_date=date(1999, 10, 20)),
        EpisodeDisplay(number=2, title=None, air_date=None),
    ]
    text = build_episode_list_text("One Piece", episodes, page=1)
    assert "Romance Dawn" in text
    assert "1999-10-20" in text
    assert "Ep 2" in text


def test_episode_list_text_handles_empty() -> None:
    text = build_episode_list_text("One Piece", [], page=1)
    assert "No episode data" in text


def test_episode_list_keyboard_back_button_uses_origin() -> None:
    keyboard = build_episode_list_keyboard(anime_id=5, page=1, has_next_page=False, origin="3")
    back = [b for row in keyboard.inline_keyboard for b in row if "anime:v:" in b.callback_data][0]
    assert back.callback_data == "anime:v:5:3"


def test_episode_list_keyboard_pagination_buttons() -> None:
    keyboard = build_episode_list_keyboard(anime_id=5, page=2, has_next_page=True, origin="-")
    callback_datas = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "ep:list:5:1:-" in callback_datas
    assert "ep:list:5:3:-" in callback_datas


def test_character_list_text_includes_role_and_va() -> None:
    characters = [CharacterDisplay(name="Luffy", role="MAIN", voice_actor_name="Mayumi Tanaka")]
    text = build_character_list_text("One Piece", characters, page=1)
    assert "Luffy" in text
    assert "Main" in text
    assert "Mayumi Tanaka" in text


def test_character_list_text_handles_no_voice_actor() -> None:
    characters = [CharacterDisplay(name="Nami", role="SUPPORTING", voice_actor_name=None)]
    text = build_character_list_text("One Piece", characters, page=1)
    assert "Nami" in text
    assert "🎙️" not in text.split("Nami")[0]  # no VA line dangling before the name


def test_character_list_keyboard_back_button() -> None:
    keyboard = build_character_list_keyboard(anime_id=5, page=1, has_next_page=False, origin="-")
    back = [b for row in keyboard.inline_keyboard for b in row if "anime:v:" in b.callback_data][0]
    assert back.callback_data == "anime:v:5:-"


def test_staff_list_text_includes_role() -> None:
    staff = [StaffDisplay(name="Eiichiro Oda", role="Original Creator")]
    text = build_staff_list_text("One Piece", staff, page=1)
    assert "Eiichiro Oda" in text
    assert "Original Creator" in text


def test_staff_list_keyboard_pagination() -> None:
    keyboard = build_staff_list_keyboard(anime_id=5, page=1, has_next_page=True, origin="2")
    callback_datas = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "staff:list:5:2:2" in callback_datas

from event_shortener.pages import EXPIRED_PAGE, NOT_ACTIVE_PAGE, NOT_FOUND_PAGE, error_page


def test_error_page_renders_fields() -> None:
    html = error_page(icon="🔗", title="Заголовок", message="Сообщение")
    assert html.startswith("<!doctype html>")
    assert 'lang="ru"' in html
    assert "🔗" in html
    assert "Заголовок" in html
    assert "Сообщение" in html


def test_prebuilt_pages_have_expected_text() -> None:
    assert "Ссылка не найдена" in NOT_FOUND_PAGE
    assert "ещё не активна" in NOT_ACTIVE_PAGE
    assert "Встреча завершена" in EXPIRED_PAGE

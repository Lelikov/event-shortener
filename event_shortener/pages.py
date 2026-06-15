"""Minimal, self-contained HTML pages for the public redirect's error states.

Browser-facing only: the redirect route returns these instead of JSON. The
content is static (no user input is interpolated), so str.format on the template
carries no injection risk.
"""

_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: #f5f7fa; color: #1f2933; padding: 24px;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .card {{
    background: #ffffff; border: 1px solid #e4e7eb; border-radius: 16px;
    padding: 40px 32px; max-width: 420px; width: 100%; text-align: center;
    box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
  }}
  .icon {{ font-size: 56px; line-height: 1; margin-bottom: 16px; }}
  h1 {{ font-size: 22px; margin: 0 0 8px; }}
  p {{ font-size: 15px; line-height: 1.5; color: #616e7c; margin: 0; }}
</style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
  </div>
</body>
</html>
"""


def error_page(*, icon: str, title: str, message: str) -> str:
    """Render the error-card HTML document."""
    return _TEMPLATE.format(icon=icon, title=title, message=message)


NOT_FOUND_PAGE = error_page(
    icon="🔗",
    title="Ссылка не найдена",
    message="Проверьте адрес ссылки.",
)
NOT_ACTIVE_PAGE = error_page(
    icon="⏳",
    title="Ссылка ещё не активна",
    message="Она откроется незадолго до начала встречи.",
)
EXPIRED_PAGE = error_page(
    icon="✅",
    title="Встреча завершена",
    message="Эта ссылка больше не активна.",
)

"""Shared web helpers: template rendering with i18n context."""
from fastapi.templating import Jinja2Templates

from app import config
from app.i18n import get_locale, translator

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def render(request, template: str, **ctx):
    lang = get_locale(request)
    ctx.update(
        request=request,
        lang=lang,
        dir="rtl" if lang == "fa" else "ltr",
        t=translator(lang),
    )
    return templates.TemplateResponse(request, template, ctx)

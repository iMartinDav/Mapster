"""Theme routes."""

from fastapi import APIRouter

from mapster.services import poster

router = APIRouter(tags=["themes"])


@router.get("/themes")
def get_themes():
    themes = []
    for theme_name in poster.get_available_themes():
        theme_data = poster.load_theme(theme_name)
        display_name = theme_data.get("name", theme_name.replace("_", " ").title())
        themes.append({
            "id": theme_name,
            "name": display_name,
            "preview_url": f"/themes/{theme_name}.png",
            **theme_data,
        })
    return {"themes": themes}

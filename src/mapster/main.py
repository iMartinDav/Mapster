"""Entrypoint: python -m mapster.main"""

import uvicorn

from mapster.config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "mapster.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import uvicorn
from auto_video_sub_infrastructure import get_settings

from auto_video_sub_api.app import create_app

app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "auto_video_sub_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    run()

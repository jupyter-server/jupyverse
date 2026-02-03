from pydantic import Field

from jupyverse_api import Config


class YRoomConfig(Config):
    document_cleanup_delay: float = Field(
        description=(
            "The time to wait (in seconds) after the last client has leaved "
            "before closing the room."
        ),
        default=60,
    )
    document_save_delay: float = Field(
        description=(
            "The time to wait (in seconds) after the last change before saving a document to disk."
        ),
        default=1,
    )

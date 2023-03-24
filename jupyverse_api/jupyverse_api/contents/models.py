from typing import Dict, List, Optional, Union

from pydantic import BaseModel


class Content(BaseModel):
    name: str
    path: str
    last_modified: Optional[str]
    created: Optional[str]
    content: Optional[Union[str, Dict, List[Dict]]]
    format: Optional[str]
    mimetype: Optional[str]
    size: Optional[int]
    writable: bool
    type: str


class SaveContent(BaseModel):
    content: Optional[Union[str, Dict]]
    format: str
    path: str
    type: str

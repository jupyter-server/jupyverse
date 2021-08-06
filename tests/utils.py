from typing import Dict, List, Optional


def create_content(
    content: Optional[List],
    type: str,
    size: Optional[int],
    mimetype: Optional[str],
    name: str,
    path: str,
    format: Optional[str],
) -> Dict:
    return {
        "content": content,
        "created": None,
        "format": format,
        "last_modified": None,
        "mimetype": mimetype,
        "name": name,
        "path": path,
        "size": size,
        "type": type,
        "writable": True,
    }


def clear_content_values(content: Dict, keys: List[str] = []):
    for k in content:
        if k in keys:
            content[k] = None
        if k == "content" and isinstance(content[k], list):
            for c in content[k]:
                clear_content_values(c, keys)
    return content


def sort_content_by_name(content: Dict):
    for k in content:
        if k == "content" and isinstance(content[k], list):
            # FIXME: this sorting algorithm is terrible!
            names = [c["name"] for c in content[k]]
            names.sort()
            new_content = []
            for name in names:
                for i, c in enumerate(content[k]):
                    if c["name"] == name:
                        break
                content[k].pop(i)
                new_content.append(c)
            content[k] = new_content
            for c in content[k]:
                sort_content_by_name(c)
    return content

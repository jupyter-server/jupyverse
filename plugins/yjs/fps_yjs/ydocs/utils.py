from typing import Union

INT = type[int]
FLOAT = type[float]


def cast_all(
    o: Union[list, dict], from_type: Union[INT, FLOAT], to_type: Union[FLOAT, INT]
) -> Union[list, dict]:
    if isinstance(o, list):
        for i, v in enumerate(o):
            if type(v) is from_type:
                v2 = to_type(v)
                if v == v2:
                    o[i] = v2
            elif isinstance(v, (list, dict)):
                cast_all(v, from_type, to_type)
    elif isinstance(o, dict):
        for k, v in o.items():
            if type(v) is from_type:
                v2 = to_type(v)
                if v == v2:
                    o[k] = v2
            elif isinstance(v, (list, dict)):
                cast_all(v, from_type, to_type)
    return o

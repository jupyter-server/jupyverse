from typing import Dict, List, Type, Union

INT = Type[int]
FLOAT = Type[float]


def cast_all(
    o: Union[List, Dict], from_type: Union[INT, FLOAT], to_type: Union[FLOAT, INT]
) -> Union[List, Dict]:
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

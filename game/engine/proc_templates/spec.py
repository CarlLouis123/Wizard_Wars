"""Validation helpers for procedural template specifications."""

from typing import Any, Dict, List, Tuple, Union
class TemplateError(Exception): pass
Color = Union[List[int], Tuple[int,int,int], str]
def _ensure_int_pair(v, key):
    if not (isinstance(v,(list,tuple)) and len(v)==2 and all(isinstance(i,int) for i in v)):
        raise TemplateError(f'"{key}" must be [int,int]'); 
    return v[0], v[1]
def _subst(value, vars_dict):
    if isinstance(value,str) and value.startswith("${") and value.endswith("}"):
        k = value[2:-1]
        if k not in vars_dict: raise TemplateError(f'Missing var "{k}"')
        return vars_dict[k]
    return value
def validate_template(tpl: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(tpl, dict): raise TemplateError("Template must be a dict.")
    if tpl.get("version") != 1: raise TemplateError('Template "version" must be 1.')
    if tpl.get("type") not in ("texture","sprite","building"): raise TemplateError('Bad "type".')
    if "name" not in tpl or not isinstance(tpl["name"], str): raise TemplateError('Need "name".')
    _ensure_int_pair(tpl.get("size", None), "size")
    layers = tpl.get("layers", [])
    if not isinstance(layers,list) or not layers: raise TemplateError('"layers" must be non-empty list.')
    tpl.setdefault("palette", []); tpl.setdefault("vars", {})
    if "tile_size" in tpl: _ensure_int_pair(tpl["tile_size"], "tile_size")
    if "seed" in tpl and not isinstance(tpl["seed"], int): raise TemplateError('"seed" must be int.')
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict) or "op" not in layer: raise TemplateError(f'Layer {i} needs "op".')
        if not isinstance(layer["op"], str): raise TemplateError(f'Layer {i} op must be string.')
    return tpl

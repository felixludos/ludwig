
try:
	from omnibelt.structured import (JSONDATA, JSONLIKE, JSONLIKEOBJ, JSONOBJ, JSONFLAT, Jsonable as AbstractJsonable,
								 flatten, unflatten, deep_get, deep_remove)

except ImportError:
	# print(f'Warning: omnibelt module is out of date.')

	from typing import Union, List, Dict, Any, Callable

	PRIMITIVES = (str, int, float, bool, type(None))
	JSONPRIMITIVE = Union[*PRIMITIVES, None]
	JSONDATA = Union[JSONPRIMITIVE, List['JSONDATA'], Dict[str, 'JSONDATA']]
	JSONOBJ = Dict[str, JSONDATA]
	JSONFLAT = Dict[str, JSONPRIMITIVE]


	class AbstractJsonable:
		def json(self) -> 'JSONLIKEOBJ':
			"""
			Return a JSON serializable representation of the object.
			"""
			raise NotImplementedError("Subclasses must implement json() method")


	JSONLIKE = Union[None, *PRIMITIVES, AbstractJsonable, List['JSONLIKE'], Dict[str, 'JSONLIKE']]
	JSONLIKEOBJ = Dict[str, JSONLIKE]


	def flatten(data: JSONOBJ, parent_key: str = '', sep: str = '.') -> JSONFLAT:
		items = {}
		for key, value in data.items() if isinstance(data, dict) else enumerate(data):
			new_key = f"{parent_key}{sep}{key}" if parent_key else key
			if isinstance(value, (dict, list)) and not isinstance(v, str):
				items.update(flatten(value, new_key, sep=sep))
			else:
				items[new_key] = value
		return items


	def unflatten(data: JSONFLAT, sep: str = '.') -> JSONOBJ:
		items = {}
		for key, value in data.items():
			keys = key.split(sep)
			d = items
			for k in keys[:-1]:
				if k not in d:
					d[k] = {} if keys[-1].isdigit() else []
				d = d[k]
			if keys[-1].isdigit():
				d.append(value)
			else:
				d[keys[-1]] = value
		return items


	_empty_json = object()


	def deep_get(data: JSONDATA, target: str, default: Any = _empty_json, *, sep: str = '.') -> Any:
		keys = target.split(sep)
		if not keys:
			if default is _empty_json:
				raise ValueError(f"Cannot get empty value for target '{target}'")
			return default
		key, *rest = keys
		if isinstance(data, dict) and key in data:
			value = data[key]
			if rest:
				return deep_get(value, sep.join(rest), default, sep=sep)
			return value
		elif isinstance(data, list) and key.isdigit() and 0 <= int(key) < len(data):
			value = data[int(key)]
			if rest:
				return deep_get(value, sep.join(rest), default, sep=sep)
			return value
		elif default is not _empty_json:
			return default
		else:
			raise KeyError(f"Key '{key}' not found in data for target '{target}'")


	def deep_remove(data: JSONDATA, target: str, *, sep: str = '.') -> Any:
		keys = target.split(sep)
		if not keys:
			raise ValueError(f"Cannot remove empty value for target '{target}'")
		key, *rest = keys
		if isinstance(data, dict) and key in data:
			return deep_remove(data[key], sep.join(rest), sep=sep) if rest else data.pop(key, None)
		elif isinstance(data, list) and key.isdigit() and 0 <= int(key) < len(data):
			key = int(key)
			if rest:
				return deep_remove(data[key], sep.join(rest), sep=sep)
			value = data[key]
			data[key] = None
			return value
		else:
			raise KeyError(f"Key '{key}' not found in data for target '{target}'")


	def jsonify(obj: JSONLIKE, *, encoder: Callable[[Any], JSONDATA] = str) -> JSONOBJ:
		"""
		Convert an object to a JSON serializable format.
		"""
		if isinstance(obj, Jsonable):
			raw = obj.json()
			return {k: jsonify(v, encoder=encoder) for k, v in raw.items()}
		elif isinstance(obj, PRIMITIVES):
			return obj
		elif isinstance(obj, (tuple, set, list)):
			return [jsonify(item, encoder=encoder) for item in obj]
		elif isinstance(obj, dict):
			return {k: jsonify(v, encoder=encoder) for k, v in obj.items()}
		elif encoder is not None:
			return encoder(obj)
		raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


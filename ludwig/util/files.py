from .imports import *



def repo_root() -> Path:
	return Path(__file__).parent.parent.parent



def hash_object_with_code(obj, include_state: bool = False) -> str:
	# https://chatgpt.com/c/67e6cc5a-56cc-8005-9fb1-cbd987573f4d
	hasher = hashlib.sha256()

	# Hash the source code of the class
	try:
		class_src = inspect.getsource(obj.__class__)
	except TypeError:
		class_src = str(obj.__class__)
	hasher.update(class_src.encode('utf-8'))

	# Optionally hash the object's state
	if include_state:
		try:
			state = pickle.dumps(obj)
		except Exception:
			state = str(obj).encode('utf-8')
		hasher.update(state)

	return hasher.hexdigest()



def hash_str(s: str) -> str:
	hasher = hashlib.sha256()
	hasher.update(s.encode('utf-8'))
	return hasher.hexdigest()



class Checkpointable:
	@property
	def name(self) -> str:
		return self.__class__.__name__

	def json(self) -> JSONOBJ:
		return {
			'code': self._behavior_hash(),
		}

	def __str__(self) -> str:
		return f'{self.name}'

	def _behavior_hash(self):
		return hash_object_with_code(self, include_state=True)

	def _checkpoint_data(self) -> JSONOBJ:
		return {
			'name': self.name,
			'code': self._behavior_hash(),
			'json': self.json(),
		}

	def _load_checkpoint_data(self, data: JSONOBJ, *, unsafe: bool = True) -> None:
		if not unsafe:
			if 'name' in data and data['name'] != self.name:
				raise ValueError(f'Checkpoint name mismatch: {data["name"]} != {self.name}')
			code = self._behavior_hash()
			if 'code' in data and data['code'] != code:
				raise ValueError(f'Checkpoint code mismatch: {data["code"]} != {code}')
		current = self.json()
		if 'json' in data and not data['json'] != current:
			print(f'WARNING: Checkpoint json mismatch: {data["json"]} != {current}')

	def checkpoint(self, path: Optional[Path] = None, *, overwrite: bool = True) -> Union[JSONOBJ, Path]:
		data = self._checkpoint_data()
		if path is None:
			return data
		if path.suffix == '': path = path.with_suffix('.json')

		if path.exists() and not overwrite:
			raise FileExistsError(f'checkpoint file already exists: {path}')

		with path.open('w') as f:
			json.dump(data, f, indent=2, sort_keys=True)

		return path

	def load_checkpoint(self, *, path: Path = None, data: Any = None,
						unsafe: bool = True) -> Optional[Path]:
		if data is None:
			assert path is not None, f'must provide path or data (not both)'
			if not path.exists() and path.suffix == '': path = path.with_suffix('.json')
			if not path.exists():
				raise FileNotFoundError(f'checkpoint file does not exist: {path}')
			with path.open('r') as f:
				data = json.load(f)
		else:
			assert path is None, f'must provide path or data (not both)'
		self._load_checkpoint_data(data, unsafe=unsafe)
		return path



import fnmatch
import hashlib
import typing
import abc
import os
import pydantic

import config_generated

ParamSet = typing.Sequence[typing.Mapping[str, typing.Any]]

class ParamsLoader(abc.ABC):
    @abc.abstractmethod
    def load_json(self, declared_path: str) -> ParamSet:
        pass

    @abc.abstractmethod
    def load_scad(self, declared_path: str) -> ParamSet:
        pass

    def load_and_merge(self, config: config_generated.ModelItem) -> ParamSet:
        combined = []

        def add(param, origin):
            param = dict(param)
            # if a parameter exists twice, drop the first one, but keep that default value.
            for i, existing in enumerate(combined):
                if existing["name"] == param["name"]:
                    combined.pop(i)
                    param["initial"] = existing["initial"]
                    break
            param["origin"] = origin
            combined.append(param)
        def add_all(params, origin):
            for p in params:
                add(p, origin)

        add_all(self.load_scad(config.file), "own")
        for path in config.additional_params:
            add_all(self.load_json(path), "additional")
        for path in config.additional_params_scad:
            add_all(self.load_scad(path), "additional")

        return combined

class Parameter:
    def __init__(self, definition: typing.Mapping[str, typing.Any], group: "GroupInfo"):
        self.definition = definition
        self.group = group
        self.metadata = config_generated.ParamMetadata()

    @property
    def name(self):
        return self.definition["name"]

def extend_merge[T: pydantic.BaseModel](base_t: T, add_t: T) -> T:
    def merge_value(base, add):
        if base is None:
            return add
        if add is None:
            return base
        if isinstance(base, list):
            return base + add
        if isinstance(base, dict):
            return merge_dict(base, add)
        return add

    def merge_dict(base, add):
        result = {}
        for key, value in base.items():
            if key in add:
                result[key] = merge_value(value, add[key])
            else:
                result[key] = value
        for key, value in add.items():
            if key not in base:
                result[key] = value
        return result

    return add_t.model_construct(**merge_dict(base_t.model_dump(), add_t.model_dump()))


class ScadContext:
    def __init__(
            self,
            config: config_generated.ModelItem,
            loader: ParamsLoader,
    ):
        self.config = config
        self.html_file = self.name() + ".html"
        self.link = self.html_file
        self.relative: str = ""  # Set later in main()

        definitions = loader.load_and_merge(config)
        groups = {}
        self.params = [
            Parameter(
                definition,
                groups.setdefault(definition["group"], GroupInfo(self, definition["group"]))
            ) for definition in definitions]
        for key, meta in config.param_metadata.items():
            any_match = False
            for candidate in self.params:
                if fnmatch.fnmatch(candidate.name, key):
                    candidate.metadata = extend_merge(candidate.metadata, meta)
                    any_match = True
            if not any_match and meta.require_present:
                raise RuntimeError(f"Parameter metadata '{key}' not found in scad files for '{self.config.file}'. If this is intentional, add require_present=false to the metadata.")

    def name(self):
        return os.path.basename(self.config.file).removesuffix(".scad")

    def group(self, name: str) -> "GroupInfo":
        return GroupInfo(self, name)

class GroupInfo:
    def __init__(self, context: ScadContext, name: str):
        self.name = name
        self.config = context.config.tab_metadata.get(name, config_generated.TabMetadata())
        self.id = hashlib.sha256(name.encode("utf-8")).hexdigest()

    def __eq__(self, other):
        return self.name == other.name

def flatten_model_configs(config: config_generated.WebOpenscadEditorConfiguration) -> typing.List[config_generated.ModelItem]:
    templates = {}

    def apply_template[T: config_generated.ModelConfig](cfg: T) -> T:
        template = templates.get(cfg.template)
        if template is None:
            if cfg.template == "default":
                return cfg
            raise RuntimeError(f"Template '{cfg.template}' not found (did you declare them in the right order?)")
        return extend_merge(template, cfg)

    for name, cfg in config.model_template.items():
        if name == "default" and len(templates) != 0:
            raise RuntimeError("Default template must be declared first (or not at all)")
        templates[name] = apply_template(cfg)
    return [apply_template(cfg) for cfg in config.model]

"""Unit tests for the domain model registry and serialization primitives."""

import pytest

from neuroca.core.models import (
    BaseModel,
    ModelID,
    ModelNotFoundError,
    ModelRegistry,
    ValidationError,
)


class ExampleModel(BaseModel):
    """Simple concrete model used for registry and serialization tests."""

    def __init__(self, *, title: str, id: str | None = None) -> None:
        self.title = title
        super().__init__(id=id)

    def validate(self) -> None:
        super().validate()
        if not self.title:
            raise ValidationError("title must be provided")


class AlternateModel(BaseModel):
    """Secondary model to exercise overwrite behaviour."""

    def __init__(self, *, description: str, id: str | None = None) -> None:
        self.description = description
        super().__init__(id=id)

    def validate(self) -> None:
        super().validate()
        if not self.description:
            raise ValidationError("description must be provided")


def test_model_id_normalisation() -> None:
    identifier = ModelID(" ExampleModel ")
    assert str(identifier) == "ExampleModel"
    assert identifier.canonical == "examplemodel"


def test_model_registry_register_and_lookup() -> None:
    registry = ModelRegistry()
    registry.register(ExampleModel, aliases={"alias-one", ModelID("alias-two")})

    assert registry.require("ExampleModel") is ExampleModel
    assert registry.require("alias-one") is ExampleModel
    assert registry.require(ModelID("ALIAS-TWO")) is ExampleModel
    assert registry.canonical_name("alias-one") == ModelID("ExampleModel").canonical
    assert registry.aliases_for(ExampleModel) == {"ExampleModel", "alias-one", "alias-two"}
    assert ModelID("examplemodel") in registry
    assert len(registry) == 1
    assert list(registry.keys()) == [ModelID("ExampleModel").canonical]
    assert list(registry.values()) == [ExampleModel]
    assert list(registry.items()) == [(ModelID("ExampleModel").canonical, ExampleModel)]
    assert registry.get("missing") is None
    assert registry.get("missing", default=ExampleModel) is ExampleModel


def test_model_registry_alias_conflicts_and_overwrite() -> None:
    registry = ModelRegistry()
    registry.register(ExampleModel, aliases={"alias"})

    registry.register(AlternateModel, name="AlternateModel")

    with pytest.raises(ValueError):
        registry.register(AlternateModel, name="ExampleModel")

    with pytest.raises(ValueError):
        registry.register(AlternateModel, aliases={"alias"})

    registry.register(AlternateModel, name="ExampleModel", overwrite=True)
    assert registry.require("ExampleModel") is AlternateModel
    assert registry.aliases_for("ExampleModel") == {"ExampleModel"}


def test_model_registry_unregister_cleans_aliases() -> None:
    registry = ModelRegistry()
    registry.register(ExampleModel, aliases={"alias"})

    removed = registry.unregister("alias")
    assert removed is ExampleModel
    assert registry.get("ExampleModel") is None
    assert ModelID("alias") not in registry
    assert len(registry) == 0

    with pytest.raises(ModelNotFoundError):
        registry.require("ExampleModel")


def test_serializable_round_trip_and_clone() -> None:
    model = ExampleModel(title="Test Title", id="model-1")
    json_payload = model.to_json()
    clone = ExampleModel.from_json(json_payload)

    assert clone.to_dict() == model.to_dict()
    assert clone.id == model.id

    mutated = model.clone(title="Updated Title")
    assert isinstance(mutated, ExampleModel)
    assert mutated.title == "Updated Title"
    assert mutated.id == model.id



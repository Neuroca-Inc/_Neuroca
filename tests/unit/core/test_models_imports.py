"""Regression tests ensuring core model exports provide concrete classes."""

from datetime import datetime

from neuroca.core.models import (
    CognitiveProfile,
    HealthMetrics,
    MemoryItem,
    MemoryMetadata,
    MetricDefinition,
    MetricType,
    SystemHealthMetrics,
    User,
    UserPreferences,
)


def test_health_metrics_updates_and_validation() -> None:
    metrics = HealthMetrics(energy_level=75, stress_level=20, fatigue=10)
    metrics.update_metric("focus_quality", 0.85)
    metrics.validate()

    assert metrics.metrics["focus_quality"] == 0.85
    assert 0.0 <= metrics.energy_level <= 100.0


def test_user_nested_models_are_instantiated() -> None:
    user = User(
        username="tester",
        email="tester@example.com",
        preferences={"theme": "dark", "notifications_enabled": False},
        cognitive_profile={"attention_span": 90, "processing_speed": 80},
        health_metrics={"energy_level": 90, "stress_level": 5, "fatigue": 12},
        tags=["beta"],
    )

    assert isinstance(user.preferences, UserPreferences)
    assert isinstance(user.cognitive_profile, CognitiveProfile)
    assert user.preferences.theme == "dark"
    assert user.cognitive_profile.attention_span == 90
    assert user.health_metrics.energy_level == 90


def test_memory_model_reexports() -> None:
    item = MemoryItem(
        content={"text": "hello"},
        metadata=MemoryMetadata(tier="stm"),
    )
    assert item.metadata.tier == "stm"
    assert item.content.primary_text == "hello"


def test_metric_models_round_trip() -> None:
    definition = MetricDefinition(
        name="request_latency",
        description="Average request latency",
        type=MetricType.GAUGE,
        unit="ms",
        labels=["route"],
    )
    definition.validate()

    payload = SystemHealthMetrics(
        state={"status": "normal", "energy_level": 90, "stress_level": 5},
        components=[{"energy_level": 90, "stress_level": 5, "fatigue": 10}],
        generated_at=datetime.utcnow(),
    )

    assert payload.state.status == "normal"
    assert payload.components[0].energy_level == 90


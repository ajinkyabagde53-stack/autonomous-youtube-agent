from src.analytics import VideoPerformance
from src.learning import LearningAgent


def test_learning_memory_aggregates_topic_retention():
    videos = [
        VideoPerformance(
            video_id="1",
            title="How to automate reports",
            average_percentage_viewed=42.0,
            ctr=4.2,
        ),
        VideoPerformance(
            video_id="2",
            title="How to automate workflows",
            average_percentage_viewed=58.0,
            ctr=5.0,
        ),
    ]

    from src.models import Opportunity

    opportunities = {
        "1": Opportunity(
            topic="automation",
            angle="automation",
            demand_signal=.5,
            audience_fit=.5,
            competition_gap=.5,
            differentiation=.5,
            business_intent=.5,
            rationale="test",
        ),
        "2": Opportunity(
            topic="automation",
            angle="automation",
            demand_signal=.5,
            audience_fit=.5,
            competition_gap=.5,
            differentiation=.5,
            business_intent=.5,
            rationale="test",
        ),
    }

    memory = LearningAgent().build_memory(videos, opportunities)

    assert memory.topic_signals["automation"]["mean"] == 50.0
    assert memory.topic_signals["automation"]["count"] == 2.0

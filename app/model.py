
from pydantic import BaseModel
from typing import List

class Recommendation(BaseModel):
    """Модель одной рекомендации"""
    track_id: int
    rank: int


class RecommendationsResponse(BaseModel):
    """Модель ответа с рекомендациями"""
    user_id: int
    recommendations: List[Recommendation]
    strategy: str
    total_count: int


class OnlineHistory(BaseModel):
    """Модель для онлайн-истории пользователя"""
    user_id: int
    track_ids: List[int]
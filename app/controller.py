from fastapi import APIRouter, Query
import service
from model import OnlineHistory, RecommendationsResponse, Recommendation

router = APIRouter()

@router.get("/")
async def root():
    return {
        "service": "Music Recommendations API",
        "endpoints": {
            "health": "/health",
            "recommendations": "/recommendations/{user_id}",
            "online_history": "/online_history (POST)"
        }
    }


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "offline_users": service.offline_recs['user_id'].nunique() if service.offline_recs is not None else 0,
        "similar_tracks_count": len(service.similar_tracks) if service.similar_tracks is not None else 0,
        "popular_tracks_count": len(service.top_popular) if service.top_popular is not None else 0
    }


@router.post("/online_history")
async def update_online_history(history: OnlineHistory):
    """
    Обновление онлайн-истории пользователя
    
    Args:
        history: Объект с user_id и списком прослушанных track_ids
        
    Returns:
        Статус обновления
    """
    service.online_history_cache[history.user_id] = history.track_ids
    return {
        "status": "success",
        "user_id": history.user_id,
        "tracks_count": len(history.track_ids)
    }


@router.get("/recommendations/{user_id}", response_model=RecommendationsResponse)
async def get_recommendations(
    user_id: int,
    n: int = Query(default=service.N_RECOMMENDATIONS, ge=1, le=100, 
                   description="Количество рекомендаций")
):
    """
    Получить персональные рекомендации для пользователя
    
    Стратегия смешивания:
    1. Если есть онлайн-история -> смешиваем онлайн и офлайн рекомендации (30%/70%)
    2. Если есть только офлайн-рекомендации -> возвращаем их
    3. Если нет персональных рекомендаций -> возвращаем популярные
    
    Args:
        user_id: ID пользователя
        n: Количество рекомендаций (по умолчанию 50)
        
    Returns:
        Объект с рекомендациями и информацией о стратегии
    """
    
    # Получаем офлайн рекомендации
    offline = service.get_offline_recommendations(user_id, n=100)  # Берём больше для смешивания
    has_offline = len(offline) > 0
    
    # Проверяем наличие онлайн-истории
    online_history = service.online_history_cache.get(user_id, [])
    has_online = len(online_history) > 0
    
    # Определяем стратегию
    if has_online and has_offline:
        # Смешиваем онлайн и офлайн
        online_recs = service.get_similar_tracks_for_history(
            online_history, 
            n=n,
            exclude_tracks=online_history
        )
        
        recommendations = service.mix_recommendations(offline, online_recs, n=n)
        strategy = "mixed_online_offline"
        
    elif has_offline:
        # Только офлайн рекомендации
        recommendations = [
            {'track_id': int(row['track_id']), 'rank': int(row['rank'])}
            for _, row in offline.head(n).iterrows()
        ]
        strategy = "offline_only"
        
    else:
        # Популярные рекомендации (fallback)
        popular = service.get_popular_recommendations(n=n, exclude_tracks=online_history)
        recommendations = [
            {'track_id': int(row['track_id']), 'rank': int(row['rank'])}
            for _, row in popular.iterrows()
        ]
        strategy = "popular_fallback"
    
    return RecommendationsResponse(
        user_id=user_id,
        recommendations=[Recommendation(**rec) for rec in recommendations],
        strategy=strategy,
        total_count=len(recommendations)
    )


@router.delete("/online_history/{user_id}")
async def clear_online_history(user_id: int):
    """
    Очистить онлайн-историю пользователя
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Статус очистки
    """
    if user_id in service.online_history_cache:
        del service.online_history_cache[user_id]
        return {"status": "success", "message": f"История пользователя {user_id} очищена"}
    
    return {"status": "not_found", "message": f"История для пользователя {user_id} не найдена"}

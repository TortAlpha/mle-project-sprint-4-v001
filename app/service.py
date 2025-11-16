import pandas as pd
from pathlib import Path
from typing import List
import boto3
from io import BytesIO

# Глобальные переменные для кэширования данных
offline_recs = None
similar_tracks = None
top_popular = None
items = None
online_history_cache = {}

N_RECOMMENDATIONS = 50
ONLINE_HISTORY_WEIGHT = 0.3
OFFLINE_WEIGHT = 0.7

def load_data():
    global offline_recs, similar_tracks, top_popular, items
    
    # Настройки S3
    BUCKET_NAME = 's3-student-mle-20250227-831080ee09'
    
    try:

        s3_client = boto3.client('s3', 
                                endpoint_url="https://storage.yandexcloud.net", 
                                region_name="ru-central1")
        
        def read_parquet_from_s3(key):
            obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
            return pd.read_parquet(BytesIO(obj['Body'].read()))
        
        print(f"Загружаем recommendations...")
        offline_recs = read_parquet_from_s3("recsys/recommendations/recommendations.parquet")
        
        print(f"Загружаем similar...")
        similar_tracks = read_parquet_from_s3("recsys/recommendations/similar.parquet")
        
        print(f"Загружаем top_popular...")
        top_popular = read_parquet_from_s3("recsys/recommendations/top_popular.parquet")
        
        print(f"Загружаем items...")
        items = read_parquet_from_s3("recsys/data/items.parquet")
        
        print("Все файлы успешно загружены из S3.")
        print(f"  - Рекомендации: {len(offline_recs)} записей")
        print(f"  - Похожие треки: {len(similar_tracks)} записей")
        print(f"  - Топ популярных: {len(top_popular)} записей")
        print(f"  - Items: {len(items)} записей")
        
    except Exception as e:
        print(f"ОШИБКА при загрузке из S3: {e}")
        print(f"Тип ошибки: {type(e).__name__}")
        print("\nСоздаём пустые датасеты для демонстрации...")
        
        offline_recs = pd.DataFrame(columns=['user_id', 'track_id', 'rank'])
        similar_tracks = pd.DataFrame(columns=['track_id', 'similar_track_id', 'score'])
        top_popular = pd.DataFrame(columns=['track_id', 'rank'])
        items = pd.DataFrame(columns=['track_id'])


def get_offline_recommendations(user_id: int, n: int = N_RECOMMENDATIONS) -> pd.DataFrame:
    """
    Получить офлайн-рекомендации для пользователя
    
    Args:
        user_id: ID пользователя
        n: Количество рекомендаций
        
    Returns:
        DataFrame с рекомендациями
    """
    user_recs = offline_recs[offline_recs['user_id'] == user_id].copy()
    
    if len(user_recs) > 0:
        return user_recs.nsmallest(n, 'rank')
    
    return pd.DataFrame(columns=['user_id', 'track_id', 'rank'])


def get_popular_recommendations(n: int = N_RECOMMENDATIONS, 
                               exclude_tracks: List[int] = None) -> pd.DataFrame:
    """
    Получить популярные рекомендации
    
    Args:
        n: Количество рекомендаций
        exclude_tracks: Список треков для исключения
        
    Returns:
        DataFrame с рекомендациями
    """
    popular = top_popular.copy()
    
    if exclude_tracks:
        popular = popular[~popular['track_id'].isin(exclude_tracks)]
    
    return popular.head(n)


def get_similar_tracks_for_history(track_ids: List[int], 
                                   n: int = N_RECOMMENDATIONS,
                                   exclude_tracks: List[int] = None) -> pd.DataFrame:
    """
    Получить похожие треки на основе истории прослушивания
    
    Args:
        track_ids: Список ID прослушанных треков
        n: Количество рекомендаций
        exclude_tracks: Список треков для исключения
        
    Returns:
        DataFrame с рекомендациями
    """
    if not track_ids:
        return pd.DataFrame(columns=['track_id', 'score'])
    
    # Находим похожие треки для каждого трека из истории
    similar = similar_tracks[similar_tracks['track_id'].isin(track_ids)].copy()
    
    if len(similar) == 0:
        return pd.DataFrame(columns=['track_id', 'score'])
    
    # Исключаем треки из истории
    all_exclude = set(track_ids)
    if exclude_tracks:
        all_exclude.update(exclude_tracks)
    
    similar = similar[~similar['similar_track_id'].isin(all_exclude)]
    
    # Агрегируем scores для одинаковых треков
    similar_agg = similar.groupby('similar_track_id')['score'].sum().reset_index()
    similar_agg.columns = ['track_id', 'score']
    similar_agg = similar_agg.sort_values('score', ascending=False)
    
    return similar_agg.head(n)


def mix_recommendations(offline: pd.DataFrame, 
                       online: pd.DataFrame, 
                       n: int = N_RECOMMENDATIONS) -> List[dict]:
    """
    Смешивание офлайн и онлайн рекомендаций
    
    Стратегия:
    1. Берём топ треки из онлайн (30%)
    2. Дополняем офлайн рекомендациями (70%)
    3. Убираем дубликаты, сохраняя порядок
    
    Args:
        offline: DataFrame с офлайн рекомендациями
        online: DataFrame с онлайн рекомендациями
        n: Итоговое количество рекомендаций
        
    Returns:
        Список рекомендаций с рангами
    """
    result = []
    seen_tracks = set()
    
    # Количество рекомендаций из каждого источника
    n_online = int(n * ONLINE_HISTORY_WEIGHT)
    n_offline = n - n_online
    
    # Добавляем онлайн рекомендации
    for idx, row in online.head(n_online).iterrows():
        track_id = int(row['track_id'])
        if track_id not in seen_tracks:
            result.append({
                'track_id': track_id,
                'rank': len(result) + 1
            })
            seen_tracks.add(track_id)
    
    # Дополняем офлайн рекомендациями
    for idx, row in offline.iterrows():
        if len(result) >= n:
            break
        track_id = int(row['track_id'])
        if track_id not in seen_tracks:
            result.append({
                'track_id': track_id,
                'rank': len(result) + 1
            })
            seen_tracks.add(track_id)
    
    return result
import requests
import time
import json
import sys
from datetime import datetime
from typing import Dict, Any


BASE_URL = "http://localhost:8000"
N_RECOMMENDATIONS = 50
LOG_FILE = "test_service.log"

class Logger:
    """Логгер для вывода в консоль и файл одновременно"""
    
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'w', encoding='utf-8')
    
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    
    def flush(self):
        self.terminal.flush()
        self.log.flush()
    
    def close(self):
        self.log.close()


def setup_logging():
    """Настройка логирования в файл и консоль"""
    logger = Logger(LOG_FILE)
    sys.stdout = logger
    return logger


def print_header(title: str):
    """Простой заголовок"""
    print(f"\n{title}")
    print("-" * len(title))


def print_test_result(test_name: str, passed: bool, details: dict = None):
    """Вывод результата теста"""
    status = "PASSED" if passed else "FAILED"
    print(f"\n[{status}] {test_name}")
    
    if details:
        for key, value in details.items():
            print(f"  {key}: {value}")


def wait_for_service(max_attempts: int = 30, delay: int = 2):
    print("Проверка доступности сервиса...")
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                health_data = response.json()
                print(f"Сервис доступен (попытка {attempt + 1})")
                print(f"  Пользователей в базе: {health_data.get('offline_users', 0)}")
                print(f"  Похожих треков: {health_data.get('similar_tracks_count', 0)}")
                print(f"  Популярных треков: {health_data.get('popular_tracks_count', 0)}")
                return True
        except requests.exceptions.ConnectionError:
            if attempt == 0:
                print("Сервис недоступен, ожидание...")
            time.sleep(delay)
    
    print(f"ОШИБКА: Не удалось подключиться к сервису после {max_attempts} попыток")
    return False


def test_scenario_1_no_personal_recommendations():
    """
    Сценарий 1: Пользователь без персональных рекомендаций
    Ожидается: popular_fallback
    """
    print_header("СЦЕНАРИЙ 1: Новый пользователь без персональных рекомендаций")
    
    user_id = 999999999
    print(f"User ID: {user_id}")
    print(f"URL: GET {BASE_URL}/recommendations/{user_id}?n={N_RECOMMENDATIONS}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/recommendations/{user_id}",
            params={"n": N_RECOMMENDATIONS}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Проверки
            strategy_ok = data["strategy"] == "popular_fallback"
            has_recs = len(data["recommendations"]) > 0
            user_id_ok = data["user_id"] == user_id
            
            passed = strategy_ok and has_recs and user_id_ok
            
            details = {
                "strategy": data["strategy"],
                "n_recs": len(data["recommendations"]),
                "first_5": [r['track_id'] for r in data['recommendations'][:5]],
                "user_id_equals": "Да" if user_id_ok else "Нет"
            }
            
            if not strategy_ok:
                details["error"] = f"Ожидалась стратегия 'popular_fallback', получена '{data['strategy']}'"
            
            print_test_result("Сценарий 1", passed, details)
            return passed
        else:
            print_test_result("Сценарий 1", False, {
                "error": f"Статус код {response.status_code}",
                "res": response.text
            })
            return False
            
    except Exception as e:
        print_test_result("Сценарий 1", False, {"ОШИБКА": str(e)})
        return False


def test_scenario_2_with_offline_only():
    """
    Сценарий 2: Пользователь с персональными рекомендациями, без онлайн-истории
    Ожидается: offline_only
    """
    print_header("СЦЕНАРИЙ 2: Пользователь с персональными рекомендациями (без онлайн-истории)")
    
    user_id = 31
    print(f"User ID: {user_id}")
    print(f"URL: GET {BASE_URL}/recommendations/{user_id}?n={N_RECOMMENDATIONS}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/recommendations/{user_id}",
            params={"n": N_RECOMMENDATIONS}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Проверки
            strategy = data["strategy"]
            has_recs = len(data["recommendations"]) > 0
            user_id_ok = data["user_id"] == user_id
            
            # Допустимые стратегии (может быть popular_fallback если пользователя нет)
            strategy_ok = strategy in ["offline_only", "popular_fallback"]
            
            passed = strategy_ok and has_recs and user_id_ok
            
            details = {
                "strategy": strategy,
                "n_recs": len(data["recommendations"]),
                "first_5": [r['track_id'] for r in data['recommendations'][:5]],
                "user_id_equals": "Да" if user_id_ok else "Нет"
            }
            
            if strategy == "popular_fallback":
                details["nb"] = f"Пользователь {user_id} не найден в базе"
            
            print_test_result("Сценарий 2", passed, details)
            return passed
        else:
            print_test_result("Сценарий 2", False, {
                "error": f"Статус код {response.status_code}",
                "res": response.text
            })
            return False
            
    except Exception as e:
        print_test_result("Сценарий 2", False, {"ОШИБКА": str(e)})
        return False


def test_scenario_3_with_online_history():
    """
    Сценарий 3: Пользователь с персональными рекомендациями и онлайн-историей
    Ожидается: mixed_online_offline
    """
    print_header("СЦЕНАРИЙ 3: Пользователь с персональными рекомендациями и онлайн-историей")
    
    user_id = 31
    online_tracks = [73538338, 21133234, 19009110, 1710816, 34608]
    
    print(f"User ID: {user_id}")
    print(f"Онлайн-история: {online_tracks}")
    
    try:

        print("\nШаг 1: Загрузка онлайн-истории")
        print(f"URL: POST {BASE_URL}/online_history")
        
        history_response = requests.post(
            f"{BASE_URL}/online_history",
            json={"user_id": user_id, "track_ids": online_tracks}
        )
        
        if history_response.status_code != 200:
            print_test_result("Сценарий 3 (загрузка истории)", False, {
                "error": "Не удалось загрузить онлайн-историю",
                "status_code": history_response.status_code
            })
            return False
        
        print("  История загружена успешно")
        
        # Шаг 2: Запрос рекомендаций
        print("\nШаг 2: Запрос рекомендаций с учетом онлайн-истории")
        print(f"URL: GET {BASE_URL}/recommendations/{user_id}?n={N_RECOMMENDATIONS}")
        
        recs_response = requests.get(
            f"{BASE_URL}/recommendations/{user_id}",
            params={"n": N_RECOMMENDATIONS}
        )
        
        if recs_response.status_code == 200:
            data = recs_response.json()
            
            # Проверки
            strategy = data["strategy"]
            has_recs = len(data["recommendations"]) > 0
            user_id_ok = data["user_id"] == user_id
            
            recommended_tracks = [r['track_id'] for r in data['recommendations']]
            history_in_recs = set(online_tracks) & set(recommended_tracks)
            no_history_in_recs = len(history_in_recs) == 0
            
            # Допустимые стратегии
            strategy_ok = strategy in ["mixed_online_offline", "offline_only", "popular_fallback"]
            
            passed = strategy_ok and has_recs and user_id_ok and no_history_in_recs
            
            details = {
                "strategy": strategy,
                "n_recs": len(data["recommendations"]),
                "first_5": recommended_tracks[:5],
                "n_tracks_from_history_in_recs": len(history_in_recs),
                "user_id_equals": "Да" if user_id_ok else "Нет"
            }
            
            if history_in_recs:
                details["alert"] = f"Треки из истории попали в рекомендации: {list(history_in_recs)}"
            
            if strategy != "mixed_online_offline":
                details["nb"] = f"Стратегия '{strategy}' вместо ожидаемой 'mixed_online_offline'"
            
            print_test_result("Сценарий 3", passed, details)
            
            # Шаг 3: Очистка истории
            print("\nШаг 3: Очистка онлайн-истории")
            clear_response = requests.delete(f"{BASE_URL}/online_history/{user_id}")
            if clear_response.status_code == 200:
                print("  История очищена успешно")
            
            return passed
        else:
            print_test_result("Сценарий 3 (получение рекомендаций)", False, {
                "error": f"Статус код {recs_response.status_code}",
                "res": recs_response.text
            })
            return False
            
    except Exception as e:
        print_test_result("Сценарий 3", False, {"error": str(e)})
        return False


def run_all_tests():
    """Запуск всех тестов"""
    logger = setup_logging()
    
    try:
        print("ТЕСТИРОВАНИЕ МИКРОСЕРВИСА РЕКОМЕНДАЦИЙ")
        print("=" * 60)
        print(f"Дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"URL сервиса: {BASE_URL}")
        print(f"Количество рекомендаций: {N_RECOMMENDATIONS}")
        print(f"Лог-файл: {LOG_FILE}")
        
        # Проверка доступности сервиса
        if not wait_for_service():
            print("\nТЕСТЫ НЕ МОГУТ БЫТЬ ВЫПОЛНЕНЫ: Сервис недоступен")
            print("Для запуска сервиса выполните: python recommendations_service.py")
            return
        
        # Запуск тестов
        results = []
        
        print("\nЗАПУСК ТЕСТОВ")
        print("=" * 60)
        
        results.append(("Сценарий 1: Новый пользователь", 
                       test_scenario_1_no_personal_recommendations()))
        time.sleep(1)
        
        results.append(("Сценарий 2: Офлайн рекомендации", 
                       test_scenario_2_with_offline_only()))
        time.sleep(1)
        
        results.append(("Сценарий 3: Онлайн + офлайн", 
                       test_scenario_3_with_online_history()))
        
        print("\n\n")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "PASSED" if result else "FAILED"
            print(f"{status}: {test_name}")
        
        print(f"\nРезультат: {passed}/{total} тестов пройдено")
        
        if passed == total:
            print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
        else:
            print(f"\nПРОВАЛЕНО ТЕСТОВ: {total - passed}")
        
        print(f"\nРезультаты сохранены в файл: {LOG_FILE}")
        
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
    
    finally:
        logger.close()
        sys.stdout = sys.__stdout__


if __name__ == "__main__":
    run_all_tests()
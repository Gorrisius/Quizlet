import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def add_user(user_id: int, username: str, first_name: str):
    try:
        supabase.table("users").upsert({
            "user_id": user_id,
            "username": username,
            "first_name": first_name
        }).execute()
    except Exception as e:
        print(f"Помилка додавання користувача: {e}")

def get_all_tests():
    try:
        response = supabase.table("tests").select("*").order("test_id").execute()
        return response.data
    except Exception as e:
        print(f"Помилка завантаження тестів: {e}")
        return []

def get_test_questions(test_id: int):
    try:
        response = (
            supabase.table("questions")
            .select("*")
            .eq("test_id", test_id)
            .order("question_id")
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"Помилка завантаження питань: {e}")
        return []

def get_question_answers(test_id: int, question_id: int):
    try:
        # Подвійна фільтрація, щоб уникнути дублікатів з інших тестів
        response = (
            supabase.table("answers")
            .select("*")
            .eq("test_id", test_id)
            .eq("question_id", question_id)
            .order("answer_id")
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"Помилка завантаження відповідей: {e}")
        return []

def save_result(user_id: int, test_id: int, score: int):
    try:
        # Спочатку видаляємо старий результат користувача для цього тесту
        supabase.table("results").delete().eq("user_id", user_id).eq("test_id", test_id).execute()
        
        # Записуємо новий результат
        supabase.table("results").insert({
            "user_id": user_id,
            "test_id": test_id,
            "score": score
        }).execute()
    except Exception as e:
        print(f"Помилка збереження результату: {e}")

def get_test_leaderboard(test_id: int):
    try:
        response = (
            supabase.table("results")
            .select("score, user_id")
            .eq("test_id", test_id)
            .order("score", desc=True)
            .limit(10)
            .execute()
        )
        
        leaderboard = []
        for row in response.data:
            user_id = row.get("user_id")
            score = row.get("score")
            
            user_response = supabase.table("users").select("first_name").eq("user_id", user_id).execute()
            name = "Невідомий"
            if user_response.data:
                name = user_response.data[0].get("first_name", "Невідомий")
                
            leaderboard.append({
                "name": name,
                "score": score
            })
            
        return leaderboard
    except Exception as e:
        print(f"Помилка завантаження лідерборду: {e}")
        return []
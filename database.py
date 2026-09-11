import os
from dotenv import load_dotenv, find_dotenv
from supabase import create_client, Client

load_dotenv(find_dotenv())

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def add_user(user_id: int, username: str, first_name: str):
    user = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if not user.data:
        supabase.table("users").insert({
            "user_id": user_id,
            "username": username,
            "first_name": first_name
        }).execute()

def get_all_tests():
    response = supabase.table("tests").select("*").execute()
    return response.data

def get_test_questions(test_id: int):
    response = supabase.table("questions").select("*").eq("test_id", test_id).order("question_id").execute()
    return response.data

def get_question_answers(question_id: int):
    response = supabase.table("answers").select("*").eq("question_id", question_id).order("answer_id").execute()
    return response.data

def save_result(user_id: int, test_id: int, score: int):
    # Шукаємо, чи є вже збережений результат цього користувача для цього тесту
    existing = supabase.table("results").select("*").eq("user_id", user_id).eq("test_id", test_id).execute()
    
    if existing.data:
        # Якщо є, беремо його ID і оновлюємо бали (старий запис перезаписується)
        result_id = existing.data[0]['result_id']
        supabase.table("results").update({
            "score": score
        }).eq("result_id", result_id).execute()
    else:
        # Якщо немає, створюємо новий запис
        supabase.table("results").insert({
            "user_id": user_id,
            "test_id": test_id,
            "score": score
        }).execute()

def get_test_leaderboard(test_id: int):
    results = supabase.table("results").select("*").eq("test_id", test_id).order("score", desc=True).limit(10).execute()
    if not results.data:
        return []
        
    user_ids = [r['user_id'] for r in results.data]
    
    users = supabase.table("users").select("*").in_("user_id", user_ids).execute()
    users_dict = {u['user_id']: u for u in users.data}
    
    leaderboard = []
    for r in results.data:
        user = users_dict.get(r['user_id'], {})
        name = user.get('first_name') or user.get('username') or "Невідомий"
        leaderboard.append({'name': name, 'score': r['score']})
        
    return leaderboard
import asyncio
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from dotenv import load_dotenv
from database import (
    add_user, get_all_tests, get_test_questions, 
    get_question_answers, save_result, get_test_leaderboard
)

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

user_test_states = {}
user_scores = {} 

MOTIVATION_PHRASES = [
    "Ти молодець! 🎉",
    "Супер! Правильно 🚀",
    "Так тримати! 👏",
    "Блискуча відповідь! ✨",
    "Ідеально! 🧠",
    "Просто вогонь! 🔥",
    "Чудова робота! 🌟",
    "Точно в ціль! 🎯"
]

class TestCallback(CallbackData, prefix="test"):
    test_id: int

class AnswerCallback(CallbackData, prefix="ans"):
    test_id: int
    question_index: int
    answer_id: int
    action: str 

class LeaderboardCallback(CallbackData, prefix="lead"):
    test_id: int

def get_main_menu(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Тести")
    builder.button(text="🏆 Таблиця лідерів")
    
    if user_id in ADMIN_IDS:
        builder.button(text="🛠 Адмін-панель")
        builder.adjust(2, 1) 
    else:
        builder.adjust(2) 
        
    return builder.as_markup(resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    await message.answer(
        f"Привіт, {message.from_user.first_name}! 👋\n"
        "Я бот для тестувань. Скористайтеся меню нижче, щоб обрати дію.",
        reply_markup=get_main_menu(message.from_user.id),
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
@dp.message(F.text == "🛠 Адмін-панель")
async def cmd_admin(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        supabase_link = os.getenv("SUPABASE_URL")
        await message.answer(
            "🛠 **Панель адміністратора**\n\n"
            "Керування тестами, питаннями та результатами відбувається безпосередньо в базі даних.\n\n"
            f"🔗 [Відкрити Supabase]({supabase_link})",
            parse_mode="Markdown"
        )
    else:
        await message.answer("У вас немає прав доступу до цієї команди. 🚫")

@dp.message(Command("tests"))
@dp.message(F.text == "📋 Тести")
async def cmd_tests(message: types.Message):
    tests = get_all_tests()
    
    if not tests:
        await message.answer("📋 Наразі список тестів порожній.")
        return
        
    text = "📋 **Доступні тести:**\nОберіть тест, який бажаєте пройти:"
    
    builder = InlineKeyboardBuilder()
    for test in tests:
        if test.get('is_active') is not False: 
            builder.button(
                text=test['title'],
                callback_data=TestCallback(test_id=test['test_id'])
            )
            
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.message(Command("leaderboard"))
@dp.message(F.text == "🏆 Таблиця лідерів")
async def cmd_leaderboard(message: types.Message):
    tests = get_all_tests()
    
    if not tests:
        await message.answer("📋 Немає доступних тестів для відображення лідерів.")
        return
        
    builder = InlineKeyboardBuilder()
    for test in tests:
        if test.get('is_active') is not False: 
            builder.button(
                text=test['title'],
                callback_data=LeaderboardCallback(test_id=test['test_id'])
            )
            
    builder.adjust(1)
    await message.answer("🏆 **Таблиця лідерів**\nОберіть тест:", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(LeaderboardCallback.filter())
async def handle_leaderboard_selection(callback: types.CallbackQuery, callback_data: LeaderboardCallback):
    leaders = get_test_leaderboard(callback_data.test_id)
    
    if not leaders:
        await callback.message.edit_text("Таблиця лідерів для цього тесту поки що порожня. Пройдіть тест першим! 🏆")
        await callback.answer()
        return
        
    text = "🏆 **ТОП-10 Гравців:**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, leader in enumerate(leaders):
        medal = medals[idx] if idx < 3 else "🏅"
        text += f"{medal} **{idx + 1}.** {leader['name']} — {leader['score']} балів\n"
        
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()

async def send_question(message: types.Message, test_id: int, questions: list, q_index: int, user_id: int):
    question = questions[q_index]
    answers = get_question_answers(test_id, question['question_id'])
    
    if user_id not in user_test_states:
        user_test_states[user_id] = []
        
    selected = user_test_states[user_id]
    q_type = question.get('question_type', 'multiple')
    hint = "(Оберіть один варіант)" if q_type == 'single' else "(Оберіть всі правильні варіанти)"
    text = f"❓ **Питання {q_index + 1} з {len(questions)}:** {hint}\n\n*{question['text']}*\n\n"
    
    builder = InlineKeyboardBuilder()
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, ans in enumerate(answers):
        num_icon = number_emojis[i] if i < len(number_emojis) else f"{i+1}."
        text += f"{num_icon} {ans['text']}\n\n"
        prefix = "✅ " if ans['answer_id'] in selected else ""
        
        builder.button(
            text=f"{prefix}{num_icon}",
            callback_data=AnswerCallback(
                test_id=test_id, 
                question_index=q_index, 
                answer_id=ans['answer_id'],
                action="toggle"
            )
        )
        
    builder.adjust(2) 
    builder.row(
        types.InlineKeyboardButton(
            text="➡️ Підтвердити відповідь",
            callback_data=AnswerCallback(
                test_id=test_id, 
                question_index=q_index, 
                answer_id=0,
                action="submit"
            ).pack()
        )
    )
    
    await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(TestCallback.filter())
async def handle_test_selection(callback: types.CallbackQuery, callback_data: TestCallback):
    test_id = callback_data.test_id
    questions = get_test_questions(test_id)
    
    if not questions:
        await callback.message.edit_text("Цей тест поки що не має питань 😔")
        await callback.answer()
        return
        
    user_id = callback.from_user.id
    user_test_states[user_id] = [] 
    user_scores[user_id] = 0 
    
    await send_question(callback.message, test_id, questions, 0, user_id)
    await callback.answer()

@dp.callback_query(AnswerCallback.filter(F.action == "toggle"))
async def handle_answer_toggle(callback: types.CallbackQuery, callback_data: AnswerCallback):
    user_id = callback.from_user.id
    ans_id = callback_data.answer_id
    
    questions = get_test_questions(callback_data.test_id)
    current_question = questions[callback_data.question_index]
    q_type = current_question.get('question_type', 'multiple')
    
    if user_id not in user_test_states:
        user_test_states[user_id] = []
        
    if q_type == 'single':
        if ans_id in user_test_states[user_id]:
            user_test_states[user_id] = [] 
        else:
            user_test_states[user_id] = [ans_id] 
    else:
        if ans_id in user_test_states[user_id]:
            user_test_states[user_id].remove(ans_id)
        else:
            user_test_states[user_id].append(ans_id)
        
    await send_question(callback.message, callback_data.test_id, questions, callback_data.question_index, user_id)
    await callback.answer()

@dp.callback_query(AnswerCallback.filter(F.action == "submit"))
async def handle_answer_submit(callback: types.CallbackQuery, callback_data: AnswerCallback):
    user_id = callback.from_user.id
    selected = user_test_states.get(user_id, [])
    
    if not selected:
        await callback.answer("Оберіть хоча б один варіант!", show_alert=True)
        return
        
    questions = get_test_questions(callback_data.test_id)
    current_question = questions[callback_data.question_index]
    all_answers = get_question_answers(callback_data.test_id, current_question['question_id'])
    
    correct_ids = [ans['answer_id'] for ans in all_answers if ans.get('is_correct')]
    feedback_text = "Відповідь прийнято! 📝" 
    
    if set(selected) == set(correct_ids):
        user_scores[user_id] = user_scores.get(user_id, 0) + 1
        feedback_text = random.choice(MOTIVATION_PHRASES)
        
    user_test_states[user_id] = []
    next_q_index = callback_data.question_index + 1
    
    if next_q_index < len(questions):
        await send_question(callback.message, callback_data.test_id, questions, next_q_index, user_id)
        await callback.answer(feedback_text)
    else:
        final_score = user_scores.get(user_id, 0)
        save_result(user_id, callback_data.test_id, final_score)
        
        await callback.message.edit_text(
            f"🎉 **Тест завершено!**\n\n"
            f"Ваш результат: **{final_score} з {len(questions)}** правильних.\n\n"
            f"Перевірте таблицю лідерів: /leaderboard", 
            parse_mode="Markdown"
        )
        user_scores.pop(user_id, None)
        await callback.answer(feedback_text)

# --- БЛОК ВЕБ-СЕРВЕРА ДЛЯ RENDER ---
async def ping_handler(request):
    return web.Response(text="Бот працює!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', ping_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Веб-сервер запущено на порту {port}")

async def main():
    print("Запуск...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
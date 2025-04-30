import json
import random
from PIL import Image
import requests
import os
from datetime import datetime
from io import BytesIO
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from telegram.ext import MessageHandler, filters

SCORE_F = 'highscores.json'

def load_score():
    if not os.path.exists(SCORE_F):
        return []
    with open(SCORE_F, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_scores(score):
    with open(SCORE_F, 'w', encoding='utf-8') as f:
        json.dump(score, f, ensure_ascii=False, indent=2)

QUIZ, SCORE, NAME = range(3)

with open('paintings.json', 'r', encoding='utf-8') as f:
    paintings = json.load(f)

user_data_store = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Простой", callback_data='difficulty|easy')],
        [InlineKeyboardButton("Cложный", callback_data='difficulty|hard')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите уровень сложности:",
        reply_markup=reply_markup
    )

async def select_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    difficulty = query.data.split('|')[1]
    user_data_store[user_id] = {
        'difficulty': difficulty
    }

    keyboard = [[InlineKeyboardButton("Начать игру", callback_data='start_quiz')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"Нажмите «Начать игру», чтобы начать игру",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    difficulty = user_data_store[user_id].get('difficulty', 'easy')
    user_data_store[user_id].update({
        'score': 0,
        'current_question': 0,
        'questions': random.sample(paintings, k=5)
    })
    await get_question(query, context)

async def get_question(query, context):
    user_id = query.from_user.id
    user_data = user_data_store[user_id]
    question_index = user_data['current_question']
    painting = user_data['questions'][question_index]
    correct_author = painting['principalOrFirstMaker']
    other_authors = list({p['principalOrFirstMaker'] for p in paintings if p['principalOrFirstMaker'] != correct_author})
    options = random.sample(other_authors, k=3) + [correct_author]
    random.shuffle(options)

    keyboard = [
        [InlineKeyboardButton(option, callback_data=f'answer|{option}')]
        for option in options
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    difficulty = user_data.get('difficulty', 'easy')

    if difficulty == 'hard':
        response = requests.get(painting['image'])
        img = Image.open(BytesIO(response.content))
        width, height = img.size
        crop_width, crop_height = int(width * 0.4), int(height * 0.4)
        left = (width - crop_width) // 2
        top = (height - crop_height) // 2
        right = left + crop_width
        bottom = top + crop_height
        cropped_img = img.crop((left, top, right, bottom))
        img_bytes = BytesIO()
        cropped_img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)

        caption = "Кто автор этой картины?"

        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=img_bytes,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        caption = f"Кто автор картины *{painting['title']}*?"
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=painting['image'],
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data = user_data_store[user_id]
    question_index = user_data['current_question']
    painting = user_data['questions'][question_index]
    correct_author = painting['principalOrFirstMaker']
    selected_author = query.data.split('|')[1]
    is_correct = (selected_author == correct_author)
    if is_correct:
        user_data['score'] += 1
    description = f"""
    Правильный ответ: *{correct_author}*
{painting['description']}
    *Место хранения*: {painting['location']}
    [Посмотреть в Google Arts]({painting['googleArtsUrl']})
    """

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=description,
        parse_mode='Markdown',
        disable_web_page_preview=False
    )
    user_data['current_question'] += 1
    if user_data['current_question'] < 5:
        await get_question(query, context)
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"Конец игры!\nВы набрали: {user_data['score']} из 5.\n\nВведите ваше имя для таблицы рекордов:"
        )
        context.user_data['awaiting_name'] = True
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_name'):
        return

    name = update.message.text.strip()[:30]
    user_id = update.message.from_user.id
    user_data = user_data_store.get(user_id)

    if not user_data:
        await update.message.reply_text("Произошла ошибка: данные викторины не найдены.")
        return
    score = user_data['score']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    highscores = load_score()
    highscores.append({
        'name': name,
        'score': score,
        'date': timestamp
    })

    highscores.sort(key=lambda x: (-x['score'], x['date']))
    highscores = highscores[:5]

    save_scores(highscores)

    leaderboard_text = "Лучшая пятёрка игроков:\n"
    for i, entry in enumerate(highscores, start=1):
        leaderboard_text += f"{i}. {entry['name']} — {entry['score']}/5 ({entry['date']})\n"
    await update.message.reply_text(leaderboard_text)

    context.user_data['awaiting_name'] = False
    del user_data_store[user_id]

if __name__ == '__main__':

    TOKEN = '7482807396:AAHAAl4mNJzfqwDOCxVJRgsOT7gXBVVnyzs'
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern='^start_quiz$'))
    app.add_handler(CallbackQueryHandler(answer, pattern=r'^answer\|'))
    app.add_handler(CallbackQueryHandler(select_difficulty, pattern=r'^difficulty\|'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name))

    print("Бот пытается работать...")
    app.run_polling()

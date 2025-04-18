import telebot
from datetime import datetime, timedelta
import time
import pytz
import threading
import json
import os
from telebot import types

# Конфигурация
TOKEN = 'YOUR_BOT_TOKEN'
GROUP_ID = 'YOUR_GROUP_ID'
ADMIN_ID = 'YOUR_ADMIN_ID'

bot = telebot.TeleBot(TOKEN)


# Загрузка данных из файлов
def load_data():
    data = {
        'week_type': None,
        'last_switch_date': None,
        'numerator': {},
        'denominator': {}
    }

    if os.path.exists('schedule_data.json'):
        with open('schedule_data.json', 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            data.update(loaded_data)

    if 'numerator' not in data:
        data['numerator'] = {
            "0": "Физика\nРусский\nХимия",
            "1": "Информатика\nОБЗР\nОбществознание",
            "2": "Математика\nБиология\nФизкультура",
            "3": "Литра\nАнглийский\nИстория",
            "4": "История\nМатематика",
            "5": "ничего",
            "6": "тоже ничего"
        }

    if 'denominator' not in data:
        data['denominator'] = {
            "0": "Физика\nРусский\nХимия",
            "1": "Информатика\nОБЗР\nОбществознание",
            "2": "Математика\nБиология\nФизкультура",
            "3": "Литра\nАнглийский\nИстория",
            "4": "История\nМатематика",
            "5": "ничего",
            "6": "тоже ничего"
        }

    return data


def save_data(data):
    with open('schedule_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


schedule_data = load_data()


def check_week_type():
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz).date()

    if schedule_data['last_switch_date']:
        last_switch = datetime.strptime(schedule_data['last_switch_date'], '%Y-%m-%d').date()
        if (now - last_switch) >= timedelta(days=7):
            schedule_data['week_type'] = 'denominator' if schedule_data['week_type'] == 'numerator' else 'numerator'
            schedule_data['last_switch_date'] = now.strftime('%Y-%m-%d')
            save_data(schedule_data)
    elif schedule_data['week_type'] is not None:
        schedule_data['last_switch_date'] = now.strftime('%Y-%m-%d')
        save_data(schedule_data)


def send_weekday_message(manual=False):
    check_week_type()

    if schedule_data['week_type'] is None:
        if str(ADMIN_ID) == ADMIN_ID:
            bot.send_message(ADMIN_ID, "⚠️ Тип недели не установлен! Используйте /admin в боте.")
        return

    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    weekday = str(now.weekday())

    current_week_type = schedule_data['week_type']
    schedule = schedule_data[current_week_type]

    week_type_name = "числитель" if current_week_type == 'numerator' else "знаменатель"
    message = f"📅 Расписание ({week_type_name}):\n{schedule[weekday]}"

    if manual:
        message = "🔔 " + message
    bot.send_message(GROUP_ID, message)


def schedule_checker():
    while True:
        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(moscow_tz)

        if now.hour == 19 and now.minute == 0:
            send_weekday_message()
            time.sleep(60)

        check_week_type()
        time.sleep(60 - now.second)


def generate_admin_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    if schedule_data['week_type'] is None:
        keyboard.add(
            types.InlineKeyboardButton(
                text="⚙️ Установить текущую неделю",
                callback_data="set_week_type"
            )
        )
    else:
        keyboard.add(
            types.InlineKeyboardButton(
                text=f"Текущая неделя: {'числитель' if schedule_data['week_type'] == 'numerator' else 'знаменатель'}",
                callback_data="show_week_info"
            )
        )

    keyboard.add(
        types.InlineKeyboardButton(
            text="📝 Редактировать числитель",
            callback_data="show_numerator"
        ),
        types.InlineKeyboardButton(
            text="📝 Редактировать знаменатель",
            callback_data="show_denominator"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            text="🚀 Отправить сообщение сейчас",
            callback_data="send_now"
        )
    )
    return keyboard


@bot.message_handler(func=lambda message: str(message.from_user.id) == ADMIN_ID)
def handle_admin_message(message):
    if message.text == '/admin':
        bot.send_message(
            message.chat.id,
            "⚙️ Панель управления:",
            reply_markup=generate_admin_keyboard()
        )
    else:
        bot.send_message(message.chat.id, "Используйте /admin для управления расписанием")


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if str(call.from_user.id) != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
        return

    if call.data.startswith('edit_numerator_'):
        day_num = call.data.split('_')[2]
        msg = bot.send_message(
            call.message.chat.id,
            f"Текущее расписание для числителя, день {day_num}:\n{schedule_data['numerator'][day_num]}\n\nВведите новое расписание:",
            reply_to_message_id=call.message.message_id
        )
        bot.register_next_step_handler(msg, process_day_rename, 'numerator', day_num)

    elif call.data.startswith('edit_denominator_'):
        day_num = call.data.split('_')[2]
        msg = bot.send_message(
            call.message.chat.id,
            f"Текущее расписание для знаменателя, день {day_num}:\n{schedule_data['denominator'][day_num]}\n\nВведите новое расписание:",
            reply_to_message_id=call.message.message_id
        )
        bot.register_next_step_handler(msg, process_day_rename, 'denominator', day_num)

    elif call.data == "set_week_type":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("Числитель", callback_data="set_numerator"),
            types.InlineKeyboardButton("Знаменатель", callback_data="set_denominator")
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Выберите текущий тип недели:",
            reply_markup=markup
        )

    elif call.data in ["set_numerator", "set_denominator"]:
        week_type = 'numerator' if call.data == "set_numerator" else 'denominator'
        schedule_data['week_type'] = week_type
        schedule_data['last_switch_date'] = datetime.now().strftime('%Y-%m-%d')
        save_data(schedule_data)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Текущая неделя установлена как: {'числитель' if week_type == 'numerator' else 'знаменатель'}",
            reply_markup=generate_admin_keyboard()
        )

    elif call.data == "show_numerator":
        schedule_text = "📝 Расписание числителя:\n\n"
        for day_num, day_schedule in sorted(schedule_data['numerator'].items()):
            schedule_text += f"День {day_num}:\n{day_schedule}\n\n"

        markup = types.InlineKeyboardMarkup()
        for day_num in sorted(schedule_data['numerator'].keys()):
            markup.add(types.InlineKeyboardButton(
                text=f"✏️ Редактировать день {day_num}",
                callback_data=f"edit_numerator_{day_num}"
            ))

        markup.add(types.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_main"
        ))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=schedule_text,
            reply_markup=markup
        )

    elif call.data == "show_denominator":
        schedule_text = "📝 Расписание знаменателя:\n\n"
        for day_num, day_schedule in sorted(schedule_data['denominator'].items()):
            schedule_text += f"День {day_num}:\n{day_schedule}\n\n"

        markup = types.InlineKeyboardMarkup()
        for day_num in sorted(schedule_data['denominator'].keys()):
            markup.add(types.InlineKeyboardButton(
                text=f"✏️ Редактировать день {day_num}",
                callback_data=f"edit_denominator_{day_num}"
            ))

        markup.add(types.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_main"
        ))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=schedule_text,
            reply_markup=markup
        )

    elif call.data == "back_to_main":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="⚙️ Панель управления:",
            reply_markup=generate_admin_keyboard()
        )

    elif call.data == "show_week_info":
        last_switch = schedule_data.get('last_switch_date', 'не установлена')
        bot.answer_callback_query(
            call.id,
            f"Тип недели: {'числитель' if schedule_data['week_type'] == 'numerator' else 'знаменатель'}\n"
            f"Дата последнего переключения: {last_switch}",
            show_alert=True
        )

    elif call.data == "send_now":
        send_weekday_message(manual=True)
        bot.answer_callback_query(call.id, "✅ Сообщение отправлено в группу!")


def process_day_rename(message, week_type, day_num):
    new_name = message.text.strip()
    schedule_data[week_type][day_num] = new_name
    save_data(schedule_data)

    # Возвращаемся к просмотру расписания после редактирования
    callback_data = "show_numerator" if week_type == "numerator" else "show_denominator"
    handle_callback(types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data=callback_data
    ))


if __name__ == "__main__":
    print("Бот запущен...")
    threading.Thread(target=schedule_checker, daemon=True).start()
    bot.infinity_polling()
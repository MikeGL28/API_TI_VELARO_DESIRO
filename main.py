import requests
import logging

from config import API_TOKEN, URL, folder_ids

from aiogram import Bot, Dispatcher, types
from aiogram.filters.callback_data import CallbackData
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from middleware import check_access

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN, session=AiohttpSession())
dp = Dispatcher()

# Глобальная переменная для хранения данных
cached_data = None


class FolderCallback(CallbackData, prefix="folder"):
    category: str

# Пагинация по страницам
def get_all_paginated_data(url, headers=None, params=None):
    all_data = []
    start = 0
    limit = 50  # Так как элементов на странице 50

    while True:
        paginated_params = {"start": start, "limit": limit}
        if params:
            paginated_params.update(params)

        try:
            response = requests.get(url, headers=headers, params=paginated_params)
            response.raise_for_status()
            data = response.json()
            if not data.get("result"):
                break
            all_data.extend(data["result"])
            start += limit
        except requests.RequestException as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            break

    return all_data

# Поиск инструкции по номеру
def search_instructions(data, search_term):
    return [
        f'<a href="{item["DOWNLOAD_URL"]}">{item["NAME"]}</a>'
        for item in data
        if search_term.lower() in item['NAME'].lower()
    ]

# Кнопки и команда /start с получением id пользователя
@dp.message(Command("start"))
@check_access
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запустил бота.")

    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text='ЭВС «Сапсан»',
        callback_data=FolderCallback(category="ЭВС «Сапсан»").pack()
    )
    keyboard.button(
        text='ЭС «Ласточка»/«Финист»',
        callback_data=FolderCallback(category="ЭС «Ласточка»/«Финист»").pack()
    )
    keyboard.adjust(2)

    await message.answer(
        "Выберите серию поезда, чтобы я мог понять, в каких папках искать инструкцию:",
        reply_markup=keyboard.as_markup()
    )


@dp.callback_query(FolderCallback.filter())
@check_access
async def process_filter(callback: types.CallbackQuery, callback_data: FolderCallback):

    category = callback_data.category  # Получаем выбранную категорию
    headers = {'Content-Type': 'application/json'}

    # Получаем ID на папку для выбранной серии поезда
    folder_id_list = folder_ids.get(category)
    if not folder_id_list:
        await callback.message.answer("Ошибка: категория не найдена.")
        return

    # Используем функцию для получения всех данных с пагинированных страниц
    global cached_data
    cached_data = [
        item
        for folder_id in folder_id_list
        for item in get_all_paginated_data(
            URL.format(folder_id=folder_id),
            headers=headers,
            params={'id': folder_id}
        )
    ]

    # Кнопка для возврата в меню
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Назад в меню"))

    await callback.message.answer(
        f"Выбрана серия поезда: {category}\n\nВведите номер инструкции:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await callback.answer()

# Кнопка назад в меню
@dp.message(lambda message: message.text == "Назад в меню")
async def handle_back_to_menu(message: types.Message):
    await send_welcome(message)


@dp.message()
@check_access
async def handle_instruction_search(message: types.Message):

    search_term = message.text.strip()  # Получаем текст сообщения (номер инструкции)

    # Используем глобальные данные, сохраненные ранее
    global cached_data
    if not cached_data:
        await message.answer("Данные не загружены. Попробуйте снова.")
        return

    # Ищем инструкции по номеру
    results = search_instructions(cached_data, search_term)
    try:
        if results:
            if len(results) > 1:
                # Если найдено несколько инструкций, отправляем их частями
                response_message = "Найдено несколько инструкций:\n\n" + "\n\n".join(results)
                await message.answer(response_message, parse_mode="HTML")
            else:
                # Если найдена одна инструкция, отправляем её
                await message.answer(results[0], parse_mode="HTML")
        else:
            await message.answer(f"Инструкция с номером '{search_term}' не найдена.")
    except Exception:
        await message.answer("Вы запрашиваете слишком большое количество инструкций. "
                             "Введите более точный номер инструкции или название.")

if __name__ == '__main__':
    dp.run_polling(bot)

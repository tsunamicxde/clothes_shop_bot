import logging
import sqlite3
import io
import uuid

from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import CallbackQuery
from aiogram.types.message import ContentType
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

import config
from execute_sql_file import execute_sql_file
from parse_price import parse_price
from escape_markdown import escape_markdown

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=config.token)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

conn = sqlite3.connect('sneaker_shop.db')
cursor = conn.cursor()

sql_files = [
    'create_users_table.sql',
    'create_global_category_table.sql',
    'create_category_table.sql',
    'create_product_table.sql',
    'create_product_photos_table.sql'
]

for sql_file in sql_files:
    execute_sql_file(cursor, sql_file)

conn.commit()

data_storage = {}


def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    catalog_button = types.InlineKeyboardButton("Каталог 🛍", callback_data="show_catalog")
    find_product_by_id_button = types.InlineKeyboardButton("Найти товар по коду 📦", callback_data="find_product_by_id")
    tracking_button = types.InlineKeyboardButton("Отслеживание 🔎", callback_data="tracking")
    channel = types.InlineKeyboardButton("Наш канал ☁️", url=config.channel_request)
    question_button = types.InlineKeyboardButton("У меня вопрос ❓️", callback_data="question")
    markup.add(catalog_button, find_product_by_id_button, tracking_button, channel, question_button)
    return markup


def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    create_global_button = types.InlineKeyboardButton("Создать глобальную категорию", callback_data="create_global")
    create_category_button = types.InlineKeyboardButton("Создать подкатегорию", callback_data="create_category")
    create_product_button = types.InlineKeyboardButton("Добавить товар", callback_data="create_product")
    delete_global_button = types.InlineKeyboardButton("Удалить глобальную категорию", callback_data="delete_global")
    delete_category_button = types.InlineKeyboardButton("Удалить подкатегорию", callback_data="delete_category")
    delete_product_button = types.InlineKeyboardButton("Удалить товар", callback_data="delete_product")
    edit_min_price_button = types.InlineKeyboardButton("Изменить минимальную цену товара", callback_data="edit_min_price")
    markup.add(create_global_button, create_category_button, create_product_button, delete_global_button, delete_category_button, delete_product_button, edit_min_price_button)
    return markup


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    existing_user = cursor.fetchone()

    await message.reply("🖐 Добро пожаловать в МАГАЗИН СБ!\n"
                        "👟 У нас вы найдете оригинальные вещи из магазина POIZON, "
                        "которые отлично дополнят ваш аутфит\n\n"
                        "✅ Приобретая вещи у нас, вы получаете не только трендовые "
                        "и оригинальные изделия, но и гарантию качества. "
                        "Команда профессионалов всегда готова помочь вам с выбором и ответить на все вопросы.\n\n"
                        "📱 Выберите пункт из меню:", reply_markup=main_menu())

    if not existing_user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()


@dp.message_handler(commands=['adm'])
async def admin_panel(message: types.Message):
    user_id = message.from_user.id
    if user_id in config.admin_ids:
        await message.reply("Вы зашли в админ-панель. Выберите опцию: ", reply_markup=admin_menu())


class CreateGlobalCategory(StatesGroup):
    waiting_for_global_category_name = State()


class CreateCategory(StatesGroup):
    waiting_for_category_name = State()
    waiting_for_parent_category_name = State()


class CreateProduct(StatesGroup):
    waiting_for_product_name = State()
    waiting_for_parse_name = State()
    waiting_for_category = State()
    waiting_for_min_price = State()
    waiting_for_photo_count = State()
    waiting_for_photos = State()


class FindProductById(StatesGroup):
    waiting_for_product_id = State()


class EditMinPrice(StatesGroup):
    waiting_for_product_id = State()
    waiting_for_min_price = State()


class DeleteProduct(StatesGroup):
    waiting_for_product_id = State()


class DeleteGlobalCategory(StatesGroup):
    waiting_for_global_category_name = State()


class DeleteCategory(StatesGroup):
    waiting_for_category_name = State()


@dp.callback_query_handler(lambda c: c.data == 'find_product_by_id')
async def find_product_by_id(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите код товара:")
    await FindProductById.waiting_for_product_id.set()
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == 'edit_min_price')
async def edit_min_price(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите код товара:")
    await EditMinPrice.waiting_for_product_id.set()
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == 'create_product')
async def create_product_command(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите название товара:")
    await CreateProduct.waiting_for_product_name.set()


@dp.callback_query_handler(lambda c: c.data == 'delete_product')
async def delete_product_command(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите код товара для удаления:")
    await DeleteProduct.waiting_for_product_id.set()


@dp.callback_query_handler(lambda c: c.data == 'delete_global')
async def delete_global_command(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите название глобальной категории для удаления:")
    await DeleteGlobalCategory.waiting_for_global_category_name.set()


@dp.callback_query_handler(lambda c: c.data == 'delete_category')
async def delete_global_command(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите название категории для удаления:")
    await DeleteCategory.waiting_for_category_name.set()


async def delete_category_and_subcategories(category_name):
    cursor.execute("SELECT id FROM product WHERE parent_category = ?", (category_name,))
    products = cursor.fetchall()

    for product in products:
        product_id = product[0]
        cursor.execute("DELETE FROM product_photos WHERE product_id = ?", (product_id,))

    cursor.execute("DELETE FROM product WHERE parent_category = ?", (category_name,))

    cursor.execute("SELECT name FROM category WHERE parent_category = ?", (category_name,))
    subcategories = cursor.fetchall()

    for subcategory in subcategories:
        subcategory_name = subcategory[0]
        await delete_category_and_subcategories(subcategory_name)

        cursor.execute("SELECT id FROM product WHERE parent_category = ?", (subcategory_name,))
        products = cursor.fetchall()

        for product in products:
            product_id = product[0]
            cursor.execute("DELETE FROM product_photos WHERE product_id = ?", (product_id,))

        cursor.execute("DELETE FROM product WHERE parent_category = ?", (category_name,))

    cursor.execute("DELETE FROM category WHERE parent_category = ?", (category_name,))


@dp.message_handler(state=DeleteCategory.waiting_for_category_name, content_types=ContentType.TEXT)
async def process_category_name_for_deletion(message: types.Message, state: FSMContext):
    category_name = message.text.strip()
    try:
        cursor.execute("SELECT id FROM category WHERE name = ?", (category_name,))
        category = cursor.fetchone()

        if not category:
            await message.reply("Категория с таким названием не найдена.")
            await state.finish()
            return

        category_id = category[0]

        await delete_category_and_subcategories(category_name)

        cursor.execute("DELETE FROM category WHERE id = ?", (category_id,))
        conn.commit()

        await message.reply(
            f"Категория '{category_name}' и все связанные подкатегории и товары успешно удалены.")
        await message.reply("Выберите опцию: ", reply_markup=admin_menu())

    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте ещё раз.")

    await state.finish()


@dp.message_handler(state=DeleteGlobalCategory.waiting_for_global_category_name, content_types=ContentType.TEXT)
async def process_global_category_name_for_deletion(message: types.Message, state: FSMContext):
    global_category_name = message.text.strip()

    try:
        cursor.execute("SELECT id FROM global_category WHERE name = ?", (global_category_name,))
        global_category = cursor.fetchone()

        if not global_category:
            await message.reply("Глобальная категория с таким названием не найдена.")
            await state.finish()
            return

        global_category_id = global_category[0]

        await delete_category_and_subcategories(global_category_name)

        cursor.execute("DELETE FROM global_category WHERE id = ?", (global_category_id,))
        conn.commit()

        await message.reply(
            f"Глобальная категория '{global_category_name}' и все связанные подкатегории и товары успешно удалены.")

        await message.reply("Выберите опцию: ", reply_markup=admin_menu())

    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте ещё раз.")

    await state.finish()


@dp.message_handler(state=DeleteProduct.waiting_for_product_id, content_types=ContentType.TEXT)
async def process_delete_product_id(message: types.Message, state: FSMContext):
    try:
        product_id = int(message.text.strip())

        cursor.execute("SELECT * FROM product WHERE id = ?", (product_id,))
        product = cursor.fetchone()

        if not product:
            await message.reply("Товар с указанным кодом не найден.")
            await state.finish()
            return

        cursor.execute("DELETE FROM product_photos WHERE product_id = ?", (product_id,))
        conn.commit()

        cursor.execute("DELETE FROM product WHERE id = ?", (product_id,))
        conn.commit()

        await message.reply(f"Товар с кодом {product_id} успешно удален.")
        await message.reply("Выберите опцию: ", reply_markup=admin_menu())
        await state.finish()
    except ValueError:
        await message.reply("Введите корректный код товара, состоящий из цифр.")
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте ещё раз.")
        await state.finish()


@dp.message_handler(state=CreateProduct.waiting_for_product_name, content_types=ContentType.TEXT)
async def process_product_name(message: types.Message, state: FSMContext):
    product_name = message.text.strip()
    async with state.proxy() as data:
        data['product_name'] = product_name

    await message.reply("Введите минимальную стоимость товара:")
    await CreateProduct.waiting_for_min_price.set()


@dp.message_handler(state=EditMinPrice.waiting_for_product_id, content_types=ContentType.TEXT)
async def process_edit_product_id(message: types.Message, state: FSMContext):
    try:
        product_id = int(message.text.strip())
        cursor.execute("SELECT * FROM product WHERE id = ?", (product_id,))
        product = cursor.fetchone()

        if not product:
            await message.reply("Товар с указанным кодом не найден.")
            await state.finish()
            return

        async with state.proxy() as data:
            data['product_id'] = product_id

        await message.reply("Введите новую минимальную цену товара:")
        await EditMinPrice.waiting_for_min_price.set()
    except ValueError:
        await message.reply("Введите корректный код товара, состоящий из цифр.")
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте ещё раз.")
        await state.finish()


@dp.message_handler(state=EditMinPrice.waiting_for_min_price, content_types=ContentType.TEXT)
async def process_edit_min_price(message: types.Message, state: FSMContext):
    try:
        async with state.proxy() as data:
            product_id = data.get('product_id')

        new_min_price = float(message.text.strip())

        cursor.execute("UPDATE product SET min_price = ? WHERE id = ?;", (new_min_price, product_id,))

        await message.reply(f"Для товара с кодом {product_id} цена изменена на {new_min_price}.")
        await state.finish()
    except ValueError:
        await message.reply("Введите корректную стоимость, состоящую из цифр.")
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте ещё раз.")
        await state.finish()


@dp.message_handler(state=FindProductById.waiting_for_product_id, content_types=ContentType.TEXT)
async def process_product_id(message: types.Message, state: FSMContext):
    try:
        product_id = int(message.text.strip())

        cursor.execute("""
            SELECT p.name, p.parse_name, p.min_price, pp.photo 
            FROM product p
            LEFT JOIN product_photos pp ON p.id = pp.product_id
            WHERE p.id = ?
        """, (product_id,))
        product_data = cursor.fetchall()

        if not product_data:
            await message.reply("Товар с указанным кодом не найден.")
            await state.finish()
            return

        product_name, parse_name, min_price = product_data[0][:3]
        photos = [photo for _, _, _, photo in product_data if photo]

        if not photos:
            await message.reply(f"Товар '{product_name}' найден, но у него нет фотографий.")
            await state.finish()
            return

        media = [types.InputMediaPhoto(media=io.BytesIO(photo)) for photo in photos]
        caption = f"Товар: {escape_markdown(product_name)}\n\n*Код товара: {product_id}*"

        chunk_size = 10
        for i in range(0, len(media), chunk_size):
            await bot.send_media_group(chat_id=message.from_user.id, media=media[i:i + chunk_size])

        data = {
            'name': product_name,
            'parse_name': parse_name
        }

        unique_id = str(uuid.uuid4())
        data_storage[unique_id] = data

        callback_data = f"parse_{unique_id}"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("Цена 💰", callback_data=callback_data))
        markup.add(types.InlineKeyboardButton("Купить 🛒", callback_data="buy"))

        await bot.send_message(message.from_user.id, caption, parse_mode='MarkdownV2', reply_markup=markup)

        await state.finish()

    except ValueError:
        await message.reply("Введите корректный код товара, состоящий из цифр:")
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте ещё раз.")


@dp.callback_query_handler(lambda c: c.data.startswith('category_'), state=CreateProduct.waiting_for_category)
async def process_category_selection(callback_query: CallbackQuery, state: FSMContext):
    category_name = callback_query.data.split('_', 1)[1]
    async with state.proxy() as data:
        data['parent_category'] = category_name

    await bot.send_message(callback_query.from_user.id, "Введите парс-название товара:")
    await CreateProduct.waiting_for_parse_name.set()


@dp.message_handler(state=CreateProduct.waiting_for_parse_name, content_types=ContentType.TEXT)
async def process_parse_name(message: types.Message, state: FSMContext):
    parse_name = message.text.strip()
    async with state.proxy() as data:
        data['parse_name'] = parse_name

    await message.reply("Введите количество фотографий товара:")
    await CreateProduct.waiting_for_photo_count.set()


@dp.message_handler(state=CreateProduct.waiting_for_photo_count, content_types=ContentType.TEXT)
async def process_photo_count(message: types.Message, state: FSMContext):
    try:
        photo_count = int(message.text.strip())
        if photo_count <= 0:
            await message.reply("Количество фото должно быть больше нуля.")
            return
        async with state.proxy() as data:
            data['photo_count'] = photo_count

        await message.reply("Отправьте фотографии товара: ")
        await CreateProduct.waiting_for_photos.set()
    except ValueError:
        await message.reply("Введите корректное количество фотографий.")


@dp.message_handler(state=CreateProduct.waiting_for_photos, content_types=ContentType.PHOTO)
async def process_photos(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        photo_count = data.get('photo_count')
        product_name = data.get('product_name')
        parse_name = data.get('parse_name')
        parent_category = data.get('parent_category')
        min_price = data.get('min_price')

        photo_file = io.BytesIO()
        await message.photo[-1].download(destination=photo_file)
        photo_file.seek(0)

        cursor.execute("SELECT id FROM product WHERE name = ? AND parent_category = ?", (product_name, parent_category))
        existing_product = cursor.fetchone()

        if existing_product:
            product_id = existing_product[0]
        else:
            cursor.execute("INSERT INTO product (name, parse_name, parent_category, min_price) VALUES (?, ?, ?, ?)",
                           (product_name, parse_name, parent_category, min_price))
            product_id = cursor.lastrowid

        cursor.execute("INSERT INTO product_photos (product_id, photo) VALUES (?, ?)", (product_id, photo_file.read()))
        conn.commit()

        data['photo_count'] -= 1

        if data['photo_count'] <= 0:
            await message.reply("Все фотографии добавлены. Товар успешно создан.")
            await message.reply("Выберите опцию: ", reply_markup=admin_menu())
            await state.finish()
        else:
            await message.reply(f"Фото добавлено. Осталось {data['photo_count']} фото.")


@dp.message_handler(state=CreateProduct.waiting_for_min_price, content_types=ContentType.TEXT)
async def process_min_price(message: types.Message, state: FSMContext):
    try:
        min_price = float(message.text.strip())
        if min_price < 0:
            await message.reply("Минимальная цена не может быть отрицательной.")
            return
        async with state.proxy() as data:
            data['min_price'] = min_price

        cursor.execute("SELECT name FROM category")
        categories = cursor.fetchall()

        if categories:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for category in categories:
                category_name = category[0]
                markup.add(types.InlineKeyboardButton(category_name, callback_data=f"category_{category_name}"))

            await message.reply("Выберите категорию для размещения товара:", reply_markup=markup)
            await CreateProduct.waiting_for_category.set()
        else:
            await message.reply("Нет доступных категорий. Пожалуйста, создайте категории сначала.")
            await state.finish()
    except ValueError:
        await message.reply("Введите корректное значение для минимальной цены.")


@dp.callback_query_handler(lambda c: c.data == 'create_global')
async def create_global_command(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите название новой глобальной категории:")
    await CreateGlobalCategory.waiting_for_global_category_name.set()


@dp.callback_query_handler(lambda c: c.data == 'create_category')
async def create_category_command(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите название новой категории:")
    await CreateCategory.waiting_for_category_name.set()


@dp.message_handler(state=CreateGlobalCategory.waiting_for_global_category_name, content_types=ContentType.TEXT)
async def process_global_category_name(message: types.Message, state: FSMContext):
    category_name = message.text.strip()

    cursor.execute("SELECT * FROM global_category WHERE name = ?", (category_name,))
    existing_category = cursor.fetchone()

    if existing_category:
        await message.reply("Такая категория уже существует.")
    else:
        cursor.execute("INSERT INTO global_category (name) VALUES (?)", (category_name,))
        conn.commit()
        await message.reply(f"Категория '{category_name}' успешно создана.")
        await message.reply("Выберите опцию: ", reply_markup=admin_menu())

    await state.finish()


@dp.message_handler(state=CreateCategory.waiting_for_category_name, content_types=ContentType.TEXT)
async def process_category_name(message: types.Message, state: FSMContext):
    category_name = message.text.strip()
    async with state.proxy() as data:
        data['category_name'] = category_name

    await message.reply("Введите название родительской категории (может быть глобальной категорией или подкатегорией):")
    await CreateCategory.waiting_for_parent_category_name.set()


@dp.message_handler(state=CreateCategory.waiting_for_parent_category_name, content_types=ContentType.TEXT)
async def process_parent_category_name(message: types.Message, state: FSMContext):
    parent_category_name = message.text.strip()
    async with state.proxy() as data:
        category_name = data['category_name']

    cursor.execute("SELECT * FROM global_category WHERE name = ?", (parent_category_name,))
    existing_global_category = cursor.fetchone()

    cursor.execute("SELECT * FROM category WHERE name = ?", (parent_category_name,))
    existing_sub_category = cursor.fetchone()

    if not existing_global_category and not existing_sub_category:
        await message.reply(f"Родительская категория '{parent_category_name}' не найдена.")
    else:
        cursor.execute("SELECT * FROM category WHERE name = ?", (category_name,))
        existing_category = cursor.fetchone()

        if existing_category:
            await message.reply("Такая категория уже существует.")
        else:
            cursor.execute("INSERT INTO category (name, parent_category) VALUES (?, ?)",
                           (category_name, parent_category_name))
            conn.commit()
            await message.reply(
                f"Категория '{category_name}' успешно создана под родительской категорией '{parent_category_name}'.")
            await message.reply("Выберите опцию: ", reply_markup=admin_menu())

    await state.finish()


@dp.callback_query_handler(lambda c: c.data == 'buy')
async def buy_product(callback_query: CallbackQuery):
    await bot.send_message(
        callback_query.from_user.id,
        f"Для покупки товара напишите менеджеру {config.manager_request}\n\n"
        f"Обязательно укажите *код товара* \\(указан внизу описания товара\\) и *размер*",
        parse_mode='MarkdownV2'
    )
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == 'tracking')
async def tracking(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, f"Обратитесь к менеджеру по поводу отслеживания заказа {config.manager_request}")
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == 'question')
async def question(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, f"По всем вопросам обращайтесь к менеджеру {config.manager_request}")
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == 'find_product_by_id')
async def question(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, f"По всем вопросам обращайтесь к менеджеру {config.manager_request}")
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == 'show_catalog')
async def show_catalog(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(previous_menu='main')
    cursor.execute("SELECT name FROM global_category")
    categories = cursor.fetchall()

    if not categories:
        await bot.answer_callback_query(callback_query.id, text="Категории отсутствуют.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for category in categories:
        category_name = category[0]
        markup.add(types.InlineKeyboardButton(category_name, callback_data=f"global_category_{category_name}"))

    markup.add(types.InlineKeyboardButton("Вернуться в главное меню ⬅️", callback_data="back_to_main"))

    await bot.send_message(callback_query.from_user.id, "Выберите категорию:", reply_markup=markup)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith('global_category_'))
async def show_subcategories(callback_query: CallbackQuery, state: FSMContext):
    category_data = callback_query.data.split('_', 2)
    category_name = category_data[2]

    await state.update_data(previous_menu='global', global_category=category_name)

    cursor.execute("SELECT name FROM category WHERE parent_category = ?", (category_name,))
    subcategories = cursor.fetchall()

    if not subcategories:
        await bot.answer_callback_query(callback_query.id, text="Подкатегории отсутствуют.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for subcategory in subcategories:
        subcategory_name = subcategory[0]
        markup.add(types.InlineKeyboardButton(subcategory_name, callback_data=f"subcategory_{subcategory_name}"))

    markup.add(types.InlineKeyboardButton("Назад ⬅️", callback_data="back_to_global"))

    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
    await bot.send_message(callback_query.from_user.id, f"Подкатегории для '{category_name}':", reply_markup=markup)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith('parse_'))
async def parse_price_handler(callback_query: CallbackQuery):
    unique_id = callback_query.data.split("_")[1]

    data = data_storage.get(unique_id)

    if data:
        name = data['name']
        parse_name = data['parse_name']
    else:
        await bot.send_message(callback_query.from_user.id, f"Цены на товар не найдены. Уточните цену у менеджера {config.manager_request}")
        return

    sent_message = await bot.send_message(callback_query.from_user.id, "Подождите, бот ищет цены на размеры...")
    try:
        cursor.execute('''
                SELECT count_of_reviews 
                FROM product 
                WHERE parse_name = ?
            ''', (parse_name,))

        result = cursor.fetchone()

        if result:
            current_count = result[0]

            if current_count is None:
                current_count = 0

            new_count = current_count + 1

            cursor.execute('''
                    UPDATE product 
                    SET count_of_reviews = ?
                    WHERE parse_name = ?
                ''', (new_count, parse_name))

            conn.commit()
        else:
            print(f"Товар с parse_name '{parse_name}' не найден.")

    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")

    cursor.execute("SELECT min_price FROM product WHERE parse_name = ?;", (parse_name,))
    min_price = cursor.fetchone()[0]
    sizes_prices = parse_price(parse_name)
    price_info = f"{escape_markdown(name)}:\n\n"
    await bot.delete_message(chat_id=callback_query.from_user.id, message_id=sent_message.message_id)
    if sizes_prices:
        for size, price in sizes_prices.items():
            price_info += f"Размер: *{escape_markdown(str(size))}* {escape_markdown("-")} Цена: *{escape_markdown(str(price))}*\n\n"
    else:
        if min_price:
            price_info += (f"Цена: от {escape_markdown(str(min_price))}\n\n"
                           f"Подробности цены на размер уточните у менеджера {escape_markdown(config.manager_request)}\n"
                           f"Обязательно укажите *размер* и *код товара*\n")
        else:
            price_info = f"Цены на товар не найдены. Уточните цену у менеджера {config.manager_request}"

    await bot.send_message(callback_query.from_user.id, price_info, parse_mode='MarkdownV2')


@dp.callback_query_handler(lambda c: c.data.startswith('subcategory_'))
async def show_sub_subcategories(callback_query: CallbackQuery, state: FSMContext):
    subcategory_name = callback_query.data.split('_')[1]
    sort_type = "increase"
    if len(callback_query.data.split("_")) > 2:
        sort_type = callback_query.data.split('_')[2]

    await state.update_data(previous_menu='subcategory', subcategory=subcategory_name)

    cursor.execute("SELECT name FROM category WHERE parent_category = ?", (subcategory_name,))
    sub_subcategories = cursor.fetchall()

    if not sub_subcategories:
        if sort_type == 'decrease':
            db_query = """
                            SELECT p.name, p.parse_name, p.id, p.min_price, pp.photo 
                            FROM product p
                            JOIN product_photos pp ON p.id = pp.product_id
                            WHERE p.parent_category = ?
                            ORDER BY p.min_price DESC
                        """
        elif sort_type == 'popularity':
            db_query = """
                                        SELECT p.name, p.parse_name, p.id, p.min_price, pp.photo 
                                        FROM product p
                                        JOIN product_photos pp ON p.id = pp.product_id
                                        WHERE p.parent_category = ?
                                        ORDER BY p.count_of_reviews DESC
                                    """
        else:
            db_query = """
                                    SELECT p.name, p.parse_name, p.id, p.min_price, pp.photo 
                                    FROM product p
                                    JOIN product_photos pp ON p.id = pp.product_id
                                    WHERE p.parent_category = ?
                                    ORDER BY p.min_price ASC
                                """

        cursor.execute(db_query, (subcategory_name,))
        products = cursor.fetchall()

        if not products:
            await bot.answer_callback_query(callback_query.id, text="Вложений не найдено.")
            return

        product_photos = {}
        for product_name, parse_name, product_id, min_price, photo_blob in products:
            if product_id not in product_photos:
                product_photos[product_id] = {
                    'name': product_name,
                    'parse_name': parse_name,
                    'min_price': min_price,
                    'photos': []
                }
            product_photos[product_id]['photos'].append(photo_blob)

        for product_id, data in product_photos.items():
            media = []
            caption = f"Товар: {escape_markdown(data['name'])}\n\n*Код товара: {product_id}*"
            for photo_blob in data['photos']:
                media.append(types.InputMediaPhoto(media=io.BytesIO(photo_blob)))

            chunk_size = 10
            for i in range(0, len(media), chunk_size):
                await bot.send_media_group(chat_id=callback_query.from_user.id, media=media[i:i + chunk_size])

            data = {
                'name': data['name'],
                'parse_name': data['parse_name']
            }

            unique_id = str(uuid.uuid4())
            data_storage[unique_id] = data

            callback_data = f"parse_{unique_id}"
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("Цена 💰", callback_data=callback_data))
            markup.add(types.InlineKeyboardButton("Купить 🛒", callback_data="buy"))

            await bot.send_message(callback_query.from_user.id, caption, parse_mode='MarkdownV2', reply_markup=markup)

        markup = types.InlineKeyboardMarkup(row_width=1)
        if sort_type == "decrease":
            markup.add(types.InlineKeyboardButton("Сортировать по возрастанию цены ⬆️",
                                                  callback_data=f"subcategory_{subcategory_name}"))
            markup.add(types.InlineKeyboardButton("Сортировать по популярности 📈",
                                                  callback_data=f"subcategory_{subcategory_name}_popularity"))
        elif sort_type == "popularity":
            markup.add(types.InlineKeyboardButton("Сортировать по возрастанию цены ⬆️",
                                                  callback_data=f"subcategory_{subcategory_name}"))
            markup.add(types.InlineKeyboardButton("Сортировать по убыванию цены ⬇️",
                                                  callback_data=f"subcategory_{subcategory_name}_decrease"))
        else:
            markup.add(types.InlineKeyboardButton("Сортировать по убыванию цены ⬇️",
                                                  callback_data=f"subcategory_{subcategory_name}_decrease"))
            markup.add(types.InlineKeyboardButton("Сортировать по популярности 📈",
                                                  callback_data=f"subcategory_{subcategory_name}_popularity"))

        markup.add(types.InlineKeyboardButton("Вернуться в каталог ⬅️", callback_data="back_to_global"))
        markup.add(types.InlineKeyboardButton("Вернуться в главное меню ⬅️", callback_data="back_to_main"))
        await bot.send_message(callback_query.from_user.id, "Выберите опцию: ", reply_markup=markup)

        await bot.answer_callback_query(callback_query.id)
    else:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for sub_subcategory in sub_subcategories:
            sub_subcategory_name = sub_subcategory[0]
            markup.add(types.InlineKeyboardButton(sub_subcategory_name, callback_data=f"subcategory_{sub_subcategory_name}"))

        markup.add(types.InlineKeyboardButton("Назад ⬅️", callback_data="back_to_subcategory"))

        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await bot.send_message(callback_query.from_user.id, f"Подкатегории для '{subcategory_name}':",
                               reply_markup=markup)

    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith('back_to_'))
async def go_back(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    previous_menu = callback_query.data.split('back_to_', 1)[1]

    if previous_menu == 'main':
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await bot.send_message(callback_query.from_user.id, "Главное меню:", reply_markup=main_menu())

    elif previous_menu == 'global':
        cursor.execute("SELECT name FROM global_category")
        categories = cursor.fetchall()

        if not categories:
            await bot.answer_callback_query(callback_query.id, text="Категории отсутствуют.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for category in categories:
            category_name = category[0]
            markup.add(types.InlineKeyboardButton(category_name, callback_data=f"global_category_{category_name}"))

        markup.add(types.InlineKeyboardButton("Вернуться в главное меню ⬅️", callback_data="back_to_main"))

        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await bot.send_message(callback_query.from_user.id, "Выберите категорию:", reply_markup=markup)

    elif previous_menu == 'subcategory':
        category_name = user_data.get('global_category')
        cursor.execute("SELECT name FROM category WHERE parent_category = ?", (category_name,))
        subcategories = cursor.fetchall()

        if not subcategories:
            await bot.answer_callback_query(callback_query.id, text="Подкатегории отсутствуют.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for subcategory in subcategories:
            subcategory_name = subcategory[0]
            markup.add(types.InlineKeyboardButton(subcategory_name, callback_data=f"subcategory_{subcategory_name}"))

        markup.add(types.InlineKeyboardButton("Назад ⬅️", callback_data="back_to_global"))

        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await bot.send_message(callback_query.from_user.id, f"Подкатегории для '{category_name}':", reply_markup=markup)

    elif previous_menu == 'sub_subcategory':
        subcategory_name = user_data.get('subcategory')
        cursor.execute("SELECT name FROM category WHERE parent_category = ?", (subcategory_name,))
        sub_subcategories = cursor.fetchall()

        if not sub_subcategories:
            await bot.answer_callback_query(callback_query.id, text="Подкатегории отсутствуют.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for sub_subcategory in sub_subcategories:
            sub_subcategory_name = sub_subcategory[0]
            markup.add(
                types.InlineKeyboardButton(sub_subcategory_name, callback_data=f"subcategory_{sub_subcategory_name}"))

        markup.add(types.InlineKeyboardButton("Назад ⬅️", callback_data="back_to_subcategory"))

        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await bot.send_message(callback_query.from_user.id, f"Подкатегории для '{subcategory_name}':",
                               reply_markup=markup)

    await bot.answer_callback_query(callback_query.id)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

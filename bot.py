import html
import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import (
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


ASK_NAME, ASK_PHONE, ASK_GENDER, ASK_SERVICE, ASK_TIME, CONFIRM, ASK_NEWS = range(7)

DEFAULT_SERVICES = [
    "Terapevt ko'rigi",
    "Kardiolog",
    "Nevropatolog",
    "Ginekolog",
    "UZI tekshiruvi",
    "Laboratoriya tahlillari",
]

DEFAULT_TIME_SLOTS = [
    "08:00 - 09:00",
    "09:00 - 10:00",
    "10:00 - 11:00",
    "11:00 - 12:00",
    "12:00 - 13:00",
    "14:00 - 15:00",
    "15:00 - 16:00",
    "16:00 - 17:00",
]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def split_env_list(name: str, default: list[str], separator: str = "|") -> list[str]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    values = [item.strip() for item in raw_value.split(separator)]
    return [item for item in values if item]


def parse_doctor_ids() -> set[int]:
    raw_value = os.getenv("DOCTOR_IDS", "").strip()
    if not raw_value:
        return set()

    doctor_ids: set[int] = set()
    for item in raw_value.split(","):
        item = item.strip()
        if item:
            doctor_ids.add(int(item))
    return doctor_ids


def database_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "appointments.sqlite3")).expanduser()


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                gender TEXT NOT NULL,
                service TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                admin_message_id INTEGER,
                confirmed_by INTEGER,
                confirmed_at TEXT
            )
            """
        )
        connection.commit()


def db_execute(path: Path, query: str, values: tuple = ()) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(query, values)
        connection.commit()


def db_fetchone(path: Path, query: str, values: tuple = ()) -> sqlite3.Row | None:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(query, values).fetchone()
    finally:
        connection.close()


def insert_appointment(path: Path, data: dict, user_id: int, username: str | None) -> int:
    connection = sqlite3.connect(path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO appointments (
                user_id, username, full_name, phone, gender,
                service, time_slot, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                user_id,
                username,
                data["full_name"],
                data["phone"],
                data["gender"],
                data["service"],
                data["time_slot"],
                now_text(),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def update_admin_message_id(path: Path, appointment_id: int, message_id: int) -> None:
    db_execute(
        path,
        "UPDATE appointments SET admin_message_id = ? WHERE id = ?",
        (message_id, appointment_id),
    )


def mark_send_failed(path: Path, appointment_id: int) -> None:
    db_execute(
        path,
        "UPDATE appointments SET status = 'send_failed' WHERE id = ?",
        (appointment_id,),
    )


def confirm_appointment_in_db(path: Path, appointment_id: int, doctor_id: int) -> None:
    db_execute(
        path,
        """
        UPDATE appointments
        SET status = 'confirmed', confirmed_by = ?, confirmed_at = ?
        WHERE id = ?
        """,
        (doctor_id, now_text(), appointment_id),
    )


def get_appointment(path: Path, appointment_id: int) -> sqlite3.Row | None:
    return db_fetchone(path, "SELECT * FROM appointments WHERE id = ?", (appointment_id,))


def get_last_appointment(path: Path, user_id: int) -> sqlite3.Row | None:
    return db_fetchone(
        path,
        """
        SELECT * FROM appointments
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    )


def get_registered_user_ids(path: Path) -> list[int]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT user_id
            FROM appointments
            WHERE user_id IS NOT NULL
            ORDER BY user_id
            """
        ).fetchall()
        return [int(row[0]) for row in rows]
    finally:
        connection.close()


def e(value: object) -> str:
    return html.escape(str(value or ""))


def private_summary(data: dict) -> str:
    return (
        "<b>Ma'lumotlaringizni tekshiring:</b>\n\n"
        f"<b>Ism familiya:</b> {e(data['full_name'])}\n"
        f"<b>Telefon:</b> {e(data['phone'])}\n"
        f"<b>Jinsi:</b> {e(data['gender'])}\n"
        f"<b>Xizmat:</b> {e(data['service'])}\n"
        f"<b>Qabul vaqti:</b> {e(data['time_slot'])}"
    )


def appointment_summary(row: sqlite3.Row) -> str:
    username = f"@{row['username']}" if row["username"] else "username yo'q"
    status = "tasdiq jarayonida" if row["status"] == "pending" else row["status"]
    return (
        f"<b>Yangi qabul arizasi #{row['id']}</b>\n\n"
        f"<b>Ism familiya:</b> {e(row['full_name'])}\n"
        f"<b>Telefon:</b> {e(row['phone'])}\n"
        f"<b>Jinsi:</b> {e(row['gender'])}\n"
        f"<b>Xizmat:</b> {e(row['service'])}\n"
        f"<b>Qabul vaqti:</b> {e(row['time_slot'])}\n"
        f"<b>Telegram:</b> {e(username)}\n"
        f"<b>Holat:</b> {e(status)}"
    )


def keyboard_from_items(prefix: str, items: list[str], columns: int = 2) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for index, item in enumerate(items):
        current_row.append(InlineKeyboardButton(item, callback_data=f"{prefix}:{index}"))
        if len(current_row) == columns:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    return InlineKeyboardMarkup(rows)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Qabulga yozilish", callback_data="book:start")],
            [InlineKeyboardButton("Ariza holatini tekshirish", callback_data="status:check")],
        ]
    )


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "Qabulga yozilish uchun botga shaxsiy xabardan /start bering."
        )
        return

    clinic_name = context.bot_data["clinic_name"]
    await update.effective_message.reply_text(
        f"Assalomu alaykum! {clinic_name} botiga hush kelibsiz.\n\n"
        "Qabulga yozilish uchun pastdagi tugmani bosing.",
        reply_markup=main_menu_keyboard(),
    )


async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()

    await query.message.reply_text(
        "Ism va familiyangizni yozing.\nMasalan: Ali Valiyev",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    full_name = (update.message.text or "").strip()
    if len(full_name) < 3:
        await update.message.reply_text("Iltimos, ism familiyangizni to'liqroq yozing.")
        return ASK_NAME

    context.user_data["full_name"] = full_name
    phone_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Telefon raqamingizni quyidagi tugma orqali yuboring.\n"
        "Qo'lda yozilgan raqam qabul qilinmaydi.",
        reply_markup=phone_keyboard,
    )
    return ASK_PHONE


async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.contact
    user = update.effective_user

    if contact.user_id and contact.user_id != user.id:
        await update.message.reply_text(
            "Iltimos, o'zingizning telefon raqamingizni tugma orqali yuboring."
        )
        return ASK_PHONE

    context.user_data["phone"] = contact.phone_number
    await update.message.reply_text(
        "Jinsingizni tanlang:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        "Variantlardan birini bosing:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Ayol", callback_data="gender:Ayol"),
                    InlineKeyboardButton("Erkak", callback_data="gender:Erkak"),
                ]
            ]
        ),
    )
    return ASK_GENDER


async def reject_manual_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Telefon raqamni yozib yubormang. Pastdagi 'Telefon raqamni yuborish' tugmasini bosing."
    )
    return ASK_PHONE


async def select_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    gender = query.data.split(":", 1)[1]
    context.user_data["gender"] = gender

    services = context.bot_data["services"]
    await query.message.reply_text(
        "Kerakli xizmatni tanlang:",
        reply_markup=keyboard_from_items("service", services),
    )
    return ASK_SERVICE


async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    services = context.bot_data["services"]
    index = int(query.data.split(":", 1)[1])
    if index < 0 or index >= len(services):
        await query.message.reply_text("Xizmat topilmadi. Qaytadan tanlang.")
        return ASK_SERVICE

    context.user_data["service"] = services[index]
    await query.message.reply_text(
        "Qabul vaqtini tanlang:",
        reply_markup=keyboard_from_items("time", context.bot_data["time_slots"]),
    )
    return ASK_TIME


async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    time_slots = context.bot_data["time_slots"]
    index = int(query.data.split(":", 1)[1])
    if index < 0 or index >= len(time_slots):
        await query.message.reply_text("Qabul vaqti topilmadi. Qaytadan tanlang.")
        return ASK_TIME

    context.user_data["time_slot"] = time_slots[index]
    await query.message.reply_text(
        private_summary(context.user_data),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Tasdiqlash", callback_data="confirm:yes")],
                [InlineKeyboardButton("Bekor qilish", callback_data="confirm:no")],
            ]
        ),
    )
    return CONFIRM


async def submit_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "confirm:no":
        context.user_data.clear()
        await query.message.reply_text(
            "Ariza bekor qilindi. Qayta yozilish uchun /start bering."
        )
        return ConversationHandler.END

    user = update.effective_user
    db_path = context.bot_data["db_path"]
    admin_group_id = context.bot_data["admin_group_id"]

    appointment_id = insert_appointment(
        db_path,
        context.user_data,
        user.id,
        user.username,
    )
    row = get_appointment(db_path, appointment_id)

    try:
        sent_message = await context.bot.send_message(
            chat_id=admin_group_id,
            text=appointment_summary(row),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Shifokor tasdiqlasin", callback_data=f"admin:confirm:{appointment_id}")]]
            ),
        )
        update_admin_message_id(db_path, appointment_id, sent_message.message_id)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Could not send appointment to admin group")
        mark_send_failed(db_path, appointment_id)
        await query.message.reply_text(
            "Ariza saqlandi, lekin admin guruhga yuborilmadi.\n"
            "ADMIN_GROUP_ID sozlamasini tekshiring.\n\n"
            f"Xatolik: {exc}"
        )
        context.user_data.clear()
        return ConversationHandler.END

    await query.message.reply_text(
        "Arizangiz qabul qilindi.\n"
        "Hozircha holat: tasdiq jarayonida.\n"
        "Shifokor tasdiqlasa, bot sizga xabar yuboradi.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Ariza holatini tekshirish", callback_data="status:check")]]
        ),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Jarayon bekor qilindi. Qayta boshlash uchun /start bering.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    row = get_last_appointment(context.bot_data["db_path"], update.effective_user.id)
    if not row:
        await update.message.reply_text(
            "Sizda hali qabul arizasi yo'q.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if row["status"] == "confirmed":
        status_text = "tasdiqlandi"
    elif row["status"] == "pending":
        status_text = "tasdiq jarayonida"
    elif row["status"] == "send_failed":
        status_text = "admin guruhga yuborishda xatolik bo'lgan"
    else:
        status_text = row["status"]

    await update.message.reply_text(
        (
            f"Oxirgi arizangiz #{row['id']} holati: {status_text}\n"
            f"Xizmat: {row['service']}\n"
            f"Qabul vaqti: {row['time_slot']}"
        ),
        reply_markup=main_menu_keyboard(),
    )


async def status_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    row = get_last_appointment(context.bot_data["db_path"], update.effective_user.id)
    if not row:
        await query.message.reply_text(
            "Sizda hali qabul arizasi yo'q.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if row["status"] == "confirmed":
        status_text = "tasdiqlandi"
    elif row["status"] == "pending":
        status_text = "tasdiq jarayonida"
    elif row["status"] == "send_failed":
        status_text = "admin guruhga yuborishda xatolik bo'lgan"
    else:
        status_text = row["status"]

    await query.message.reply_text(
        (
            f"Oxirgi arizangiz #{row['id']} holati: {status_text}\n"
            f"Xizmat: {row['service']}\n"
            f"Qabul vaqti: {row['time_slot']}"
        ),
        reply_markup=main_menu_keyboard(),
    )


async def chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await update.effective_message.reply_text(
        f"Chat ID: {chat.id}\n"
        f"Nomi: {chat.title or chat.full_name}\n"
        f"Turi: {chat.type}"
    )


async def doctor_can_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    doctor_ids = context.bot_data["doctor_ids"]

    if doctor_ids:
        return user_id in doctor_ids

    try:
        member = await context.bot.get_chat_member(context.bot_data["admin_group_id"], user_id)
    except Exception:  # noqa: BLE001
        return False

    return member.status in {"administrator", "creator"}


async def start_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.id != context.bot_data["admin_group_id"]:
        await update.effective_message.reply_text(
            "Yangilik yuborish komandasi faqat qabul arizalar guruhida ishlaydi."
        )
        return ConversationHandler.END

    if not await doctor_can_confirm(update, context):
        await update.effective_message.reply_text("Sizda yangilik yuborish huquqi yo'q.")
        return ConversationHandler.END

    prompt = await update.effective_message.reply_text(
        "Yangilik matnini yoki rasm+matnni shu xabarga Reply qilib yuboring.\n"
        "Rasm yuborsangiz, matnni rasm captioniga yozing.\n"
        "Bekor qilish uchun /cancel yozing.",
        reply_markup=ForceReply(
            selective=True,
            input_field_placeholder="Yangilik matni yoki rasm captioni",
        ),
    )
    context.user_data["news_prompt_message_id"] = prompt.message_id
    return ASK_NEWS


async def broadcast_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message

    if update.effective_chat.id != context.bot_data["admin_group_id"]:
        return ConversationHandler.END

    if not await doctor_can_confirm(update, context):
        await message.reply_text("Sizda yangilik yuborish huquqi yo'q.")
        return ConversationHandler.END

    if message.photo and not message.caption:
        await message.reply_text(
            "Rasmga yangilik matnini caption qilib yozing, keyin qayta yuboring."
        )
        return ASK_NEWS

    user_ids = get_registered_user_ids(context.bot_data["db_path"])
    if not user_ids:
        await message.reply_text("Hali qabulga yozilgan userlar yo'q.")
        return ConversationHandler.END

    sent_count = 0
    failed_count = 0
    for user_id in user_ids:
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
            )
            sent_count += 1
        except Exception:  # noqa: BLE001
            failed_count += 1
            logging.exception("Could not send news to user_id=%s", user_id)

    await message.reply_text(
        "Yangilik yuborildi.\n"
        f"Yuborildi: {sent_count} ta\n"
        f"Yuborilmadi: {failed_count} ta"
    )
    context.user_data.pop("news_prompt_message_id", None)
    return ConversationHandler.END


async def cancel_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("news_prompt_message_id", None)
    await update.effective_message.reply_text("Yangilik yuborish bekor qilindi.")
    return ConversationHandler.END


async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if update.effective_chat.id != context.bot_data["admin_group_id"]:
        await query.answer("Bu tugma faqat admin guruhda ishlaydi.", show_alert=True)
        return

    if not await doctor_can_confirm(update, context):
        await query.answer("Sizda tasdiqlash huquqi yo'q.", show_alert=True)
        return

    appointment_id = int(query.data.rsplit(":", 1)[1])
    row = get_appointment(context.bot_data["db_path"], appointment_id)
    if not row:
        await query.answer("Ariza topilmadi.", show_alert=True)
        return

    if row["status"] == "confirmed":
        await query.answer("Bu ariza oldin tasdiqlangan.", show_alert=True)
        return

    confirm_appointment_in_db(context.bot_data["db_path"], appointment_id, update.effective_user.id)
    confirmed_row = get_appointment(context.bot_data["db_path"], appointment_id)

    await query.edit_message_text(
        appointment_summary(confirmed_row)
        + f"\n\n<b>Tasdiqladi:</b> {e(update.effective_user.full_name)}",
        parse_mode=ParseMode.HTML,
    )

    user_message = (
        "Qabul arizangiz tasdiqlandi.\n\n"
        f"Xizmat: {confirmed_row['service']}\n"
        f"Qabul vaqti: {confirmed_row['time_slot']}\n"
        "Belgilangan vaqtda kelishingizni so'raymiz."
    )

    try:
        await context.bot.send_message(chat_id=confirmed_row["user_id"], text=user_message)
        await query.answer("Userga tasdiq xabari yuborildi.")
    except Exception:  # noqa: BLE001
        logging.exception("Could not notify user")
        await query.answer(
            "Ariza tasdiqlandi, lekin userga xabar yuborib bo'lmadi.",
            show_alert=True,
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Unhandled bot error", exc_info=context.error)


def build_application() -> Application:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin_group_id = os.getenv("ADMIN_GROUP_ID", "").strip()

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN .env faylida ko'rsatilmagan.")
    if not admin_group_id:
        raise RuntimeError("ADMIN_GROUP_ID .env faylida ko'rsatilmagan.")

    db_path = database_path()
    init_db(db_path)

    application = Application.builder().token(token).build()
    application.bot_data["clinic_name"] = os.getenv("CLINIC_NAME", "Shifokor qabul")
    application.bot_data["admin_group_id"] = int(admin_group_id)
    application.bot_data["doctor_ids"] = parse_doctor_ids()
    application.bot_data["services"] = split_env_list("SERVICES", DEFAULT_SERVICES)
    application.bot_data["time_slots"] = split_env_list("TIME_SLOTS", DEFAULT_TIME_SLOTS)
    application.bot_data["db_path"] = db_path

    conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_booking, pattern="^book:start$")],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, receive_phone),
                MessageHandler(filters.ALL, reject_manual_phone),
            ],
            ASK_GENDER: [CallbackQueryHandler(select_gender, pattern="^gender:")],
            ASK_SERVICE: [CallbackQueryHandler(select_service, pattern="^service:")],
            ASK_TIME: [CallbackQueryHandler(select_time, pattern="^time:")],
            CONFIRM: [CallbackQueryHandler(submit_appointment, pattern="^confirm:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    news_conversation = ConversationHandler(
        entry_points=[CommandHandler("yangilik", start_news)],
        states={
            ASK_NEWS: [
                MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, broadcast_news)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_news)],
        allow_reentry=True,
    )

    application.add_handler(CommandHandler("start", welcome))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("chatid", chat_id))
    application.add_handler(CallbackQueryHandler(status_button, pattern="^status:check$"))
    application.add_handler(CallbackQueryHandler(admin_confirm, pattern="^admin:confirm:"))
    application.add_handler(news_conversation)
    application.add_handler(conversation)
    application.add_error_handler(error_handler)

    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    application = build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

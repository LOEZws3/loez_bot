import html
import datetime
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.admin_utils import is_admin
from utils.user_utils import remove_user, reset_changes_count
from utils.role_utils import get_role_by_id, find_roles, load_roles_status, save_roles_status

logger = logging.getLogger(__name__)
router = Router()

# ======================== /findrole ========================

@router.message(Command('findrole'))
async def cmd_findrole(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Используйте: /findrole [запрос]\n\n"
            "Можно искать по:\n"
            "• названию роли (частично)\n"
            "• @юзернейму владельца\n"
            "• ID владельца\n"
            "• имени владельца"
        )
        return

    query = parts[1].strip()
    results = find_roles(query)

    if not results:
        await message.answer(f"❌ По запросу <b>{html.escape(query)}</b> ничего не найдено.", parse_mode="HTML")
        return

    if len(results) > 10:
        text = f"🔍 <b>Найдено {len(results)} ролей</b> (показаны первые 10):\n\n"
        results = results[:10]
    else:
        text = f"🔍 <b>Найдено: {len(results)}</b>\n\n"

    buttons = []
    for r in results:
        role_name = r['name']
        role_id = r.get('id')
        if not role_id:
            continue
        status_emoji = "🟢" if r['status'] == 'свободна' else "🔴" if r['status'] == 'занята' else "⏳"
        buttons.append([InlineKeyboardButton(
            text=f"{status_emoji} {role_name} ({r['season']})",
            callback_data=f"findrole_view_{role_id}"
        )])

    await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.regexp(r"^findrole_view_\d+$"))
async def findrole_view(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    try:
        role_id = int(callback.data.replace("findrole_view_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка ID роли.", show_alert=True)
        return

    role_info = get_role_by_id(role_id)
    if not role_info:
        await callback.message.edit_text("❌ Роль не найдена.")
        return

    role_name = role_info.get('name')
    status = role_info.get('status', '?')
    season = role_info.get('season', '?')
    owner_id = role_info.get('owner_id')
    username = role_info.get('username', '')

    full_name = '—'
    if owner_id:
        from utils.user_utils import get_user_by_id
        user_data = get_user_by_id(int(owner_id))
        if user_data:
            full_name = user_data.get('full_name', '—')

    status_emoji = "🟢" if status == 'свободна' else "🔴" if status == 'занята' else "⏳"

    text = (
        f"🎭 <b>Роль: {html.escape(role_name)}</b>\n\n"
        f"📁 Сезон: {html.escape(season)}\n"
        f"{status_emoji} Статус: {status}\n"
    )

    if owner_id:
        text += f"\n👤 <b>Владелец:</b>\n"
        text += f"• Имя: {html.escape(full_name)}\n"
        text += f"• Юзернейм: @{username if username else 'нет'}\n"
        text += f"• ID: <code>{owner_id}</code>\n"
    else:
        text += f"\n👤 Владелец: нет\n"

    buttons = [[InlineKeyboardButton(text="🔙 К поиску", callback_data="findrole_back")]]

    if owner_id:
        buttons.insert(0, [InlineKeyboardButton(
            text="🗑️ Удалить роль и юзера",
            callback_data=f"findrole_delete_{role_id}"
        )])

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except Exception:
        pass

@router.callback_query(F.data.regexp(r"^findrole_delete_yes_\d+$"))
async def findrole_delete_do(callback: CallbackQuery):
    logger.info(f"🔵 [findrole_delete_do] ENTERED, data={callback.data}, user={callback.from_user.id}")
    try:
        await callback.answer("⏳ Удаляю...")
    except Exception:
        pass

    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    try:
        role_id = int(callback.data.replace("findrole_delete_yes_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка ID роли.", show_alert=True)
        return

    role_info = get_role_by_id(role_id)
    if not role_info or not role_info.get('owner_id'):
        try:
            await callback.message.edit_text("❌ Роль уже свободна или не найдена.")
        except Exception:
            pass
        return

    owner_id = int(role_info.get('owner_id'))
    role_name = role_info.get('name')

    status_data = load_roles_status()
    for key, info in status_data.items():
        if isinstance(info, dict) and info.get('id') == role_id:
            status_data[key]['status'] = 'свободна'
            status_data[key]['owner_id'] = None
            status_data[key]['username'] = None
            break
    save_roles_status(status_data)

    removed = remove_user(owner_id)
    try:
        reset_changes_count(owner_id)
    except Exception:
        pass

    logger.info(f"ℹ️ Тег у {owner_id} не удалён: Telegram Bot API не поддерживает set_chat_member_tag")

    response = f"✅ <b>Роль «{html.escape(role_name)}» удалена:</b>\n"
    response += f"• 📌 Роль освобождена\n"
    if removed:
        response += f"• 👤 Юзер <code>{owner_id}</code> удалён из users.json\n"
    response += f"• 🏷️ Тег в чате: <i>не поддерживается API</i>\n"
    response += f"• 🔄 Счётчик смен сброшен"

    try:
        await callback.message.edit_text(response, parse_mode="HTML")
    except Exception:
        try:
            await callback.message.answer(response, parse_mode="HTML")
        except Exception:
            pass

    logger.info(f"Админ {admin_id} удалил роль ID {role_id} и юзера {owner_id}")

@router.callback_query(F.data.regexp(r"^findrole_delete_\d+$"))
async def findrole_delete_confirm(callback: CallbackQuery):
    logger.info(f"🔵 [findrole_delete_confirm] ENTERED, data={callback.data}")
    try:
        await callback.answer()
    except Exception:
        pass

    admin_id = callback.from_user.id
    if not is_admin(admin_id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    try:
        role_id = int(callback.data.replace("findrole_delete_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка ID роли.", show_alert=True)
        return

    role_info = get_role_by_id(role_id)
    if not role_info or not role_info.get('owner_id'):
        await callback.message.edit_text("❌ Роль уже свободна или не найдена.")
        return

    owner_id = role_info.get('owner_id')
    role_name = role_info.get('name')

    try:
        await callback.message.edit_text(
            f"⚠️ <b>Вы уверены?</b>\n\n"
            f"Роль: <b>{html.escape(role_name)}</b>\n"
            f"Владелец ID: <code>{owner_id}</code>\n\n"
            f"Будет удалено:\n"
            f"• Роль → статус «свободна»\n"
            f"• Юзер из users.json\n"
            f"• Тег в чате\n"
            f"• Счётчик смен\n\n"
            f"История (users_history) сохранится.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"findrole_delete_yes_{role_id}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="findrole_back")
                ]
            ])
        )
    except Exception as e:
        logger.warning(f"⚠️ [findrole_delete_confirm] edit_text упал: {e}")

@router.callback_query(F.data == "findrole_back")
async def findrole_back(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            "🔍 Для нового поиска используйте /findrole [запрос]"
        )
    except Exception:
        pass

# ============================================================
# ⚠️ НОВОЕ: /giverest (Отправить в рест за юзера)
# ============================================================

@router.message(Command('giverest'))
async def cmd_giverest(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ Доступ запрещён.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Используйте: /giverest [ID юзера] [дней]\n"
            "Пример: /giverest 8076284478 3"
        )
        return

    try:
        target_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("❌ Неверные аргументы. Введите числа.")
        return

    if days < 1 or days > 30:
        await message.answer("❌ Количество дней должно быть от 1 до 30.")
        return

    # Ищем роль этого юзера
    status_data = load_roles_status()
    found_role_key = None
    for role_key, info in status_data.items():
        if isinstance(info, dict) and info.get('owner_id') == target_id:
            found_role_key = role_key
            break

    if not found_role_key:
        await message.answer(f"❌ У пользователя {target_id} нет активной роли.")
        return

    # Выставляем рест
    end_date = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()

    status_data[found_role_key]['status'] = 'рест'
    status_data[found_role_key]['extra'] = end_date
    save_roles_status(status_data)

    await message.answer(
        f"✅ <b>Пользователь отправлен в рест!</b>\n\n"
        f"👤 Юзер: <code>{target_id}</code>\n"
        f"🎭 Роль: {html.escape(found_role_key)}\n"
        f"📅 До: {end_date} ({days} дн.)",
        parse_mode="HTML"
    )

    # Пробуем уведомить юзера в ЛС
    try:
        await message.bot.send_message(
            target_id,
            f"⏳ <b>Администратор отправил вас в рест.</b>\n\n"
            f"🎭 Роль: <b>{html.escape(found_role_key)}</b>\n"
            f"📅 Вернуться: <b>{end_date}</b> ({days} дн.)",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить {target_id} о ресте: {e}")

    logger.info(f"Админ {user_id} отправил {target_id} в рест на {days} дней")
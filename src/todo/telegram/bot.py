"""Telegram bot: add/list todos from your phone.

Long-polls Telegram (no public endpoint needed) and shells out to the local
`todo` CLI. Single-user: only TELEGRAM_ALLOWED_USER_ID may talk to it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

if TYPE_CHECKING:
    from telegram import Update

from ..core.config import get_app_config
from .cli_bridge import (
    TodoCliError,
    format_add_reply,
    format_list_reply,
    is_authorized,
    run_todo_json,
)

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Send any text to add it as a todo.\n"
    "/list - show your active todos\n"
    "/help - this message"
)


async def _guard(update: Update, allowed_user_id: int | None) -> bool:
    user = update.effective_user
    if is_authorized(user.id if user else None, allowed_user_id):
        return True
    logger.warning(
        "Rejected message from unauthorized user %s", user.id if user else "?"
    )
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed = context.bot_data["allowed_user_id"]
    if not await _guard(update, allowed):
        return
    await update.message.reply_text(HELP_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def list_todos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed = context.bot_data["allowed_user_id"]
    if not await _guard(update, allowed):
        return
    try:
        data = run_todo_json("ls")
    except TodoCliError as exc:
        await update.message.reply_text(str(exc))
        return
    await update.message.reply_text(format_list_reply(data))


async def add_todo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed = context.bot_data["allowed_user_id"]
    if not await _guard(update, allowed):
        return
    text = update.message.text.strip()
    if not text:
        return
    try:
        data = run_todo_json("add", text)
    except TodoCliError as exc:
        await update.message.reply_text(str(exc))
        return
    await update.message.reply_text(format_add_reply(data))


def build_application(bot_token: str, allowed_user_id: int | None) -> Application:
    application = Application.builder().token(bot_token).build()
    application.bot_data["allowed_user_id"] = allowed_user_id

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler(["list", "ls"], list_todos))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_todo))
    return application


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = get_app_config()
    if not config.telegram.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    if not config.telegram.allowed_user_id:
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID is not set")

    application = build_application(
        config.telegram.bot_token, config.telegram.allowed_user_id
    )
    logger.info("todo telegram bot starting (long polling)")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

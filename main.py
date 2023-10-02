from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)

import os
from dotenv import load_dotenv

from error_handlers import error_handler
from admin_commands import start_command, help_command, cancel_command
from unknown_response import unknown_command, unknown_text
from handler import handle_callback_query, handle_text
from task import add_task

load_dotenv()

EXPECT_TEXT = range(1)

if __name__ == "__main__":
    TOKEN = os.getenv("TOKEN") or ""
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("task", add_task))
    app.add_handler(CommandHandler("cancel", cancel_command))

    app.add_handler(CallbackQueryHandler(handle_callback_query))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT, handle_text)],
        states={EXPECT_TEXT: [MessageHandler(filters.TEXT, handle_text)]},
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    app.add_handler(conv_handler)

    # Unknown
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_handler(MessageHandler(filters.TEXT, unknown_text))

    # Errors
    app.add_error_handler(error_handler)

    # Polls the bot
    app.run_polling(poll_interval=3, allowed_updates=Update.ALL_TYPES)
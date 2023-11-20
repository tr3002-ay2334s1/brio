from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler
from flows.night_flow import night_flow_review
from lib.api_handler import get_user
from lib.google_cal import (
    get_calendar_events,
    get_google_cal_link,
    get_readable_cal_event_str,
)
from utils.constants import DAY_END_TIME, DAY_START_TIME, NEW_YORK_TIMEZONE_INFO
from utils.get_name_time_from_job_name import get_name_time_from_job_name
from utils.job_queue import add_once_job
from utils.logger_config import configure_logger
from utils.update_cron_jobs import update_cron_jobs
from utils.utils import (
    send_message,
    send_on_error_message,
    update_chat_data_state,
    update_chat_data_state_context,
)

logger = configure_logger()


@update_chat_data_state_context
async def block_start_alert(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job is None:
        logger.error("context.job is None for block_alert")
        await send_on_error_message(context)
        return
    if context.job.name is None:
        logger.error("context.job.name is None for block_alert")
        await send_on_error_message(context)
        return
    if context.chat_data is None:
        logger.error("context.chat_data is None for block_alert")
        await send_on_error_message(context)
        return

    keyboard = [
        [
            InlineKeyboardButton("Ok!", callback_data="block_start_alert_confirm"),
        ],
        [
            InlineKeyboardButton(
                "Change of Plans",
                callback_data="block_flow_schedule_edit",
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    name, time = get_name_time_from_job_name(context.job.name)

    await send_message(
        None,
        context,
        "It's almost " + time[:2] + ":" + time[-2:] + ". Time to work on " + name,
        reply_markup=reply_markup,
    )


@update_chat_data_state
async def block_start_alert_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data is None:
        logger.error("context.chat_data is None for block_start_alert_confirm")
        await send_on_error_message(context)
        return
    if context.job is None:
        logger.error("context.job is None for block_start_alert_confirm")
        await send_on_error_message(context)
        return
    if context.job.name is None:
        logger.error("context.job.name is None for block_start_alert_confirm")
        await send_on_error_message(context)
        return

    name, time = get_name_time_from_job_name(context.job.name)

    # get block end time
    user_id = context.chat_data["chat_id"]
    user = get_user(user_id)
    events = get_calendar_events(
        refresh_token=user.get("google_refresh_token", ""),
        q=name,
        k=1
    )
    if len(events) != 1:
        logger.error("Failed to find block")
        await send_on_error_message(context)
        return
    block = events[0]

    await add_once_job(
        callback=block_end_alert,
        when=(datetime.fromisoformat(
            block.get("end").get("dateTime", datetime.now(tz=NEW_YORK_TIMEZONE_INFO))
        )),
        chat_id=context.chat_data["chat_id"],
        context=context,
        data=name,
    )

    await send_message(
        update,
        context,
        "Great!",
    )

    return ConversationHandler.END


@update_chat_data_state
async def block_flow_schedule_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data is None:
        logger.error("context.chat_data is None for block_flow_schedule_edit")
        await send_on_error_message(context)
        return

    user_id = context.chat_data["chat_id"]
    url = get_google_cal_link(user_id)

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data="block_flow_schedule_edit_yes"),
        ],
        [
            InlineKeyboardButton(
                "Click me to go to Google Calendar",
                url=url,
            ),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_message(
        update,
        context,
        "Have you edited?",
        reply_markup=reply_markup,
    )


@update_chat_data_state
async def block_flow_schedule_updated(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if context.chat_data is None:
        logger.error("context.chat_data is None for event_creation")
        await send_on_error_message(context)
        return

    # TODO: sync gcal with database

    user_id = context.chat_data["chat_id"]
    user = get_user(user_id)
    events = get_calendar_events(
        refresh_token=user.get("google_refresh_token", None),
        timeMin=datetime.combine(
            datetime.now(tz=NEW_YORK_TIMEZONE_INFO).date(),
            DAY_START_TIME,
            tzinfo=NEW_YORK_TIMEZONE_INFO,
        ).isoformat(),
        timeMax=datetime.combine(
            datetime.now(tz=NEW_YORK_TIMEZONE_INFO).date(),
            DAY_END_TIME,
            tzinfo=NEW_YORK_TIMEZONE_INFO,
        ).isoformat(),
        k=150,
    )
    schedule = get_readable_cal_event_str(events) or "No upcoming events found."

    await update_cron_jobs(context)

    await send_message(
        update,
        context,
        "Updated your schedule!\n\n" + schedule,
    )

    await block_next_alert(update, context)


@update_chat_data_state
async def block_next_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data is None:
        logger.error("context.chat_data is None for event_creation")
        await send_on_error_message(context)
        return

    user_id = context.chat_data["chat_id"]
    user = get_user(user_id)
    events = get_calendar_events(
        refresh_token=user.get("google_refresh_token", None),
        timeMin=datetime.combine(
            datetime.now(tz=NEW_YORK_TIMEZONE_INFO).date(),
            DAY_START_TIME,
            tzinfo=NEW_YORK_TIMEZONE_INFO,
        ).isoformat(),
        timeMax=datetime.combine(
            datetime.now(tz=NEW_YORK_TIMEZONE_INFO).date(),
            DAY_END_TIME,
            tzinfo=NEW_YORK_TIMEZONE_INFO,
        ).isoformat(),
        k=150,
    )

    has_upcoming_block = len(events) == 0

    if has_upcoming_block:
        task = ""
        time = ""
        await send_message(
            update,
            context,
            "Nice job! Next up you have " + task + " at " + time,
        )
    else:
        await night_flow_review(update, context)


@update_chat_data_state_context
async def block_end_alert(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job is None:
        logger.error("context.job is None for block_start_alert_confirm")
        await send_on_error_message(context)
        return
    if context.job.name is None:
        logger.error("context.job.name is None for block_start_alert_confirm")
        await send_on_error_message(context)
        return
    
    name, time = get_name_time_from_job_name(context.job.name)

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data="block_end_alert_yes"),
        ],
        [
            InlineKeyboardButton("No", callback_data="block_end_alert_no"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_message(
        None,
        context,
        "Time's up! Did you get " + name + " done?",
        reply_markup=reply_markup,
    )


@update_chat_data_state
async def block_end_alert_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_message(
        update,
        context,
        "How much more time do you need? (in minutes)",
    )


@update_chat_data_state
async def block_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data is None:
        logger.error("context.chat_data is None for block_update")
        await send_on_error_message(context)
        return

    duration = context.chat_data["block_update"]["duration"]
    # TODO: checks for the first free slot
    time = ""

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data="block_update_yes"),
        ],
        [
            InlineKeyboardButton("No", callback_data="block_update_no"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await send_message(
        update,
        context,
        "You have some time at " + time + ". Would you like to work on it then?",
        reply_markup=reply_markup,
    )


@update_chat_data_state
async def block_created(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: create new event on gcal
    # add_calendar_item

    await block_flow_schedule_updated(update, context)

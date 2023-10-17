import pytz
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from ai import plan_tasks
from google_cal import get_calendar_events, get_login_google, refresh_daily_jobs_with_google_cal

from logger_config import configure_logger

logger = configure_logger()

from datetime import datetime, timedelta

from task import task_dateline, end_add_task
from job_queue import add_daily_job, add_once_job
from google_oauth_utils import google_login, login_start
from database import add_task, fetch_user
from morning_flow import (
    direct_to_google_calendar,
    morning_flow_event,
    morning_flow_event_edit,
    morning_flow_event_update,
    morning_flow_next_event,
    morning_flow_new_task,
)
from night_flow import (
    night_flow_review,
    night_flow_feeling,
    night_flow_favourite,
    night_flow_proud,
    night_flow_improve,
    night_flow_next_day_schedule,
    night_flow_pick_time,
    night_flow_invalid_time,
    night_flow_skip,
    night_flow_end,
    night_flow_next_day_schedule_edit,
)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        logger.info(
            "handle_callback_query: None\n"
            + "update: "
            + str(update)
            + "\ncontext: "
            + str(context)
        )
        return

    await query.answer()

    logger.info("handle_callback_query: " + str(query.data))

    # first_time
    if query.data == "google_login":
        await login_start(update, context)
    if query.data == "morning_flow_events_acknowledge":
        # save morning_flow_events_acknowledge here - not mvp
        return ConversationHandler.END
    elif query.data == "morning_flow_events_edit":
        return ConversationHandler.END
    elif query.data == "morning_flow_event_acknowledge":
        await refresh_daily_jobs_with_google_cal(update=update, context=context, user_id=None)
        return ConversationHandler.END
    elif query.data == "morning_flow_event_edit":
        await morning_flow_event_edit(update, context)
    elif query.data == "morning_flow_event_edit_yes":
        await refresh_daily_jobs_with_google_cal(update=update, context=context, user_id=None)
        await morning_flow_event_update(update, context)
    elif query.data == "morning_flow_event_end_yes":
        await morning_flow_next_event(update, context)
    elif query.data == "morning_flow_event_end_no":
        await direct_to_google_calendar(update, context, callback="morning_flow_event_edit")
        # await morning_flow_event_edit(update, context)
    elif query.data == "morning_flow_new_task_yes":
      await refresh_daily_jobs_with_google_cal(update=update, context=context, user_id=None)
      await morning_flow_event_update(update, context)
    elif query.data == "morning_flow_new_task_no":
        await morning_flow_event_edit(update, context)
    elif (
        query.data == "night_flow_review_yes"
        or query.data == "night_flow_new_review_time_yes"
    ):
        await night_flow_feeling(update, context)
    elif query.data == "night_flow_review_no":
        await night_flow_pick_time(update, context)
    elif query.data == "night_flow_new_review_time_skip":
        await night_flow_skip(update, context)
    elif query.data == "night_flow_next_day_schedule_ok":
        await night_flow_end(update, context)
    elif query.data == "night_flow_next_day_schedule_edit":
        await direct_to_google_calendar(update, context, callback="night_flow_next_day_schedule_edit_2")
    elif query.data == "night_flow_next_day_schedule_edit_2":
        await night_flow_next_day_schedule_edit(update, context)
    elif query.data == "night_flow_next_day_schedule_edit_yes":
        plan_tasks(telegram_user_id=query.from_user.id)
        await night_flow_next_day_schedule(update, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message is None or update.effective_message.text is None:
        logger.info("handle_text: None " + str(update))
        return

    text = update.effective_message.text

    logger.info("handle_text: " + str(text))

    chat_data = context.chat_data
    state = chat_data.get("state") if chat_data is not None else ""

    logger.info("state: " + str(state))

    if state == "add_task":
        add_task(telegram_user_id=update.message.from_user.id, name=text)
        await end_add_task(update, context)
    elif state == "night_flow_feeling":
        # save night_flow_feeling here -- not mvp
        await night_flow_favourite(update, context)
    elif state == "night_flow_favourite":
        # save night_flow_favourite here -- not mvp
        await night_flow_proud(update, context)
    elif state == "night_flow_proud":
        # save night_flow_proud here -- not mvp
        await night_flow_improve(update, context)
    elif state == "night_flow_improve":
        await night_flow_next_day_schedule(update, context)
    elif state == "night_flow_pick_time":
        return await validate_night_flow_pick_time(update, context, text)
    elif state == "night_flow_invalid_time":
        return await validate_night_flow_pick_time(update, context, text)


async def validate_night_flow_pick_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
):
    if text == None:
        await night_flow_invalid_time(update, context)
    else:
        try:
            # Parse the input to a datetime object.
            input_time = datetime.strptime(text, "%H%M").time()

            # Get current datetime and time.
            current_datetime = datetime.now()
            current_time = current_datetime.time()

            # Create datetime objects for comparison.
            current_dt = datetime.combine(current_datetime.date(), current_time)
            input_dt = datetime.combine(current_datetime.date(), input_time)

            # Check if input time is earlier than the current time.
            # If yes, assume it's for the next day.
            if input_dt <= current_dt:
                input_dt += timedelta(days=1)

                # Calculate the number of seconds from now till the input time.
            delta_seconds = (input_dt - current_dt).seconds

            if update.effective_chat is None:
                logger.info("update.effective_chat: None")
                return

            await add_once_job(
                night_flow_review, delta_seconds, update.effective_chat.id, context
            )

            return ConversationHandler.END
        except ValueError:
            # Invalid time format; invoke the night_flow_invalid_time function.
            await night_flow_invalid_time(update, context)

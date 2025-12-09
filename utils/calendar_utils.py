import calendar
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CALENDAR_CALLBACK = "CAL_"

def create_calendar(year=None, month=None):
    """
    Creates an inline keyboard with the provided year and month.
    """
    now = datetime.datetime.now()
    if year is None: year = now.year
    if month is None: month = now.month
    
    markup = []
    
    # First row - Month and Year
    row = [
        InlineKeyboardButton(calendar.month_name[month] + " " + str(year), callback_data="IGNORE")
    ]
    markup.append(row)
    
    # Second row - Week Days (Su Mo Tu ...)
    days = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] # US Convention matches calendar.monthcalendar? No, calendar uses 0=Mo
    # Correcting for calendar module (0=Monday) to match typical US/Global expectation or just stick to ISO.
    # Let's stick to simple text.
    days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    row = [InlineKeyboardButton(day, callback_data="IGNORE") for day in days]
    markup.append(row)
    
    # Calendar rows - Days of Month
    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
            else:
                # Format: CAL_action_year_month_day
                # Action: DAY
                row.append(InlineKeyboardButton(str(day), callback_data=f"{CALENDAR_CALLBACK}DAY_{year}_{month}_{day}"))
        markup.append(row)
        
    # Last row - Previous / Next Month buttons
    row = []
    
    # Prev Month
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    row.append(InlineKeyboardButton("<<", callback_data=f"{CALENDAR_CALLBACK}PREV_{prev_year}_{prev_month}"))
    
    # Ignore center
    row.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
    
    # Next Month
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    row.append(InlineKeyboardButton(">>", callback_data=f"{CALENDAR_CALLBACK}NEXT_{next_year}_{next_month}"))
    
    markup.append(row)
    
    return InlineKeyboardMarkup(markup)

def process_calendar_selection(update, context):
    """
    Process the callback query.
    Returns (ret_data, success Boolean)
    ret_data is a date string 'YYYY-MM-DD' if success is True.
    """
    query = update.callback_query
    data = query.data
    # data format: CAL_ACTION_...
    
    _, action, *args = data.split("_")
    
    if action == "IGNORE":
        query.answer()
        return None, False
        
    elif action == "DAY":
        year, month, day = map(int, args)
        selected_date = datetime.date(year, month, day)
        query.answer()
        return selected_date.strftime("%Y-%m-%d"), True
        
    elif action == "PREV" or action == "NEXT":
        year, month = map(int, args)
        new_keyboard = create_calendar(year, month)
        query.edit_message_reply_markup(reply_markup=new_keyboard)
        query.answer() # Just nav, no selection
        return None, False

    return None, False

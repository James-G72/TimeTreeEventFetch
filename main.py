"""Run basic commands to access TimeTree data."""
import os
import requests
import datetime as dt

from utils import details_from_config, get_session, milli_since_e
from api_details import API_URL, API_AGENT
from time_tree_struct import TTCalendar, TTEvent

CONFIG_PATH = os.path.join(os.getcwd(), "config.txt")


def fetch_calendars(s_id, name_filter=None):
    """
    Perform a TimeTree API request to get the list of all calendars for the logged-in User.
    :param s_id: Session ID for the login.
    :return: List of TTCalendar objects for all calendars found.
    """
    session = requests.Session()
    session.cookies.set("_session_id",s_id)
    url = f"{API_URL}/calendars?since=0"
    response = session.get(
        url,
        headers={
            "Content-Type":"application/json",
            "X-Timetreea":API_AGENT,
        },
    )
    if response.status_code != 200:
        print("Failed to get calendar metadata")

    cal_list = []
    for cal in response.json()["calendars"]:
        if name_filter:
            if cal["name"] == name_filter:
                cal_list.append(TTCalendar(session_id=s_id, response_dict=cal))
        else:
            cal_list.append(TTCalendar(session_id=s_id, response_dict=cal))

    return cal_list


def plot_calendar(calendar_tt):
    """
    Plot the events within a TTCalendar visually.
    :param calendar_tt: TTCalendar object populated with events.
    :return: None
    """


def main(config_path):
    """Test functionality by requesting and printing calendar events."""
    login_dict = details_from_config(config_path)

    sessionn_id = get_session(login_dict)

    print(f"TimeTree API Session ID is: {sessionn_id}")

    calendars = fetch_calendars(sessionn_id, name_filter="Ruth")

    start = milli_since_e(dt.datetime.now() - dt.timedelta(weeks=4))
    end = milli_since_e(dt.datetime.now())

    for calendar in calendars:
        calendar.fetch_events(start, end)

    print(f"Found the following events between {dt.datetime.fromtimestamp(start/1000).strftime('%Y-%m-%d %H:%M:%S.%f')} and {dt.datetime.fromtimestamp(end/1000).strftime('%Y-%m-%d %H:%M:%S.%f')}:")
    for event in calendar.events:
        print(f"{dt.datetime.fromtimestamp(event.start/1000).strftime('%Y-%m-%d %H:%M:%S')} - {event.title}")


if __name__ == "__main__":
    main(CONFIG_PATH)

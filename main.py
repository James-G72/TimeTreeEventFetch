"""Run basic commands to access TimeTree data."""
import os
import requests
import datetime as dt
import tabulate
import time

from api_details import API_URL, API_AGENT
from time_tree_struct import TTCalendar, TTEvent, TTTime, round_tttime_to_day
from utils import details_from_config, get_session

CONFIG_PATH = os.path.join(os.getcwd(), "config.txt")

DATE_FMT = "%d-%b-%Y %H:%M"


def fetch_calendars(logins: dict, name_filter=None):
    """
    Perform a TimeTree API request to get the list of all calendars for the logged-in User.
    :param logins: Dictionary of login details.
    :param name_filter: If provided, then filter for only calendars with that name.
    :return: List of TTCalendar objects for all calendars found.
    """
    session_id = get_session(logins)

    print(f"TimeTree API Session ID is: {session_id}")

    session = requests.Session()
    session.cookies.set("_session_id", session_id)
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
                cal_list.append(TTCalendar(session_id=session_id, response_dict=cal, login=logins))
        else:
            cal_list.append(TTCalendar(session_id=session_id, response_dict=cal, login=logins))

    return cal_list


def run_live_view(calendar: TTCalendar, refresh_interval_s: int):
    """
    Print the events to the command line and refresh the view periodically.
    :param calendar: Calendar to be queried and displayed.
    :param refresh_interval_s: integer of seconds after which to perform a sync.
    :return: None
    """
    disp_start = TTTime(dt_object=dt.datetime.now() - dt.timedelta(days=1))
    disp_end = TTTime(dt_object=dt.datetime.now() + dt.timedelta(days=7))

    # If no start and end times are passed to the fetch_events function then all events are fetched.
    calendar.fetch_events()

    relevant_events = calendar.events_between_dates(disp_start, disp_end, full_day=True)

    print(" -- Initialising Loop for Displaying Events --")
    update_count = 0
    # TODO add in some sort of exit feature
    while 1:
        print(f" -- Printing Events between {round_tttime_to_day(disp_start).as_dt().strftime(DATE_FMT)} and "
              f"{round_tttime_to_day(disp_end).as_dt().strftime(DATE_FMT)} -- ")
        print(f"Update {update_count}: {dt.datetime.now().strftime('%H:%M:%S')}")
        print_events(relevant_events, calendar.recur_events, calendar.deleted_events, calendar.label_data, calendar.known_users)

        # Wait for the required interval before refreshing
        time.sleep(refresh_interval_s)
        calendar.fetch_events()
        relevant_events = calendar.events_between_dates(disp_start, disp_end, full_day=True)
        update_count += 1


def print_events(events: list, recur_events: list, deleted_events: list, labels: dict, users: dict):
    """
    Print a list of events in chronological order with nice formatting.
    :param events: List of TTEvent objects to be printed.
    :param recur_events: List of all recurring events that could be parents of TTEventRecurs
    :param deleted_events: List of all events that have been deleted from the Calendar since the programme was initialised.
    :param labels: List of label information.
    :param users: List of author information.
    :return: None
    """
    # Creating tabulate header and table list
    headers = ["Date", "Title", "Label", "Author"]
    entries = []
    for event in events:
        if isinstance(event, TTEvent):
            entries.append(
                [event.start.as_dt().strftime(DATE_FMT),
                 event.title,
                 labels[event.label_id]["name"],
                 users[event.author_id],
                ]
            )
        else: # Then we have a TTEventRecur object
            parent_event = None
            for tte in recur_events:
                if tte.id == event.parent_id:
                    parent_event = tte
            if not parent_event:
                raise ValueError(f"TTEventRecur with title {event.title} has no parent.")
            entries.append(
                [event.start.as_dt().strftime(DATE_FMT),
                 event.title,
                 labels[parent_event.label_id]["name"],
                 users[parent_event.author_id],
                ]
            )

    # Reordering the table by event start time
    date_time_entries = [[dt.datetime.strptime(e[0],DATE_FMT), idx] for idx, e in enumerate(entries)]
    sorted_entries_with_idx = sorted(date_time_entries)
    sorted_entries = [entries[e[1]] for e in sorted_entries_with_idx]

    print(tabulate.tabulate(sorted_entries, headers, tablefmt="simple_outline", colalign=("centre",)))

    # Print events that have been deleted recently
    if deleted_events is not None:
        print("Events deleted:")
        for e in deleted_events:
            print(f"    {e.title}")


def main(config_path):
    """
    Test functionality by requesting and printing calendar events.
    :param config_path: Full file path to the config.txt file with login details.
    :return: None
    """
    login_dict = details_from_config(config_path)

    # This line assumes that there is only one calendar called Ruth
    main_calendar = fetch_calendars(login_dict, name_filter="Ruth")[0]

    run_live_view(main_calendar, 10)


if __name__ == "__main__":
    main(CONFIG_PATH)


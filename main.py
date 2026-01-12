"""Run basic commands to access TimeTree data."""
import os
import requests
import datetime as dt
import matplotlib.pyplot as plt
from matplotlib.dates import datestr2num, DateFormatter, DayLocator
from matplotlib.ticker import AutoMinorLocator
from matplotlib.patches import Patch
import tabulate
import time

from utils import details_from_config, get_session
from api_details import API_URL, API_AGENT
from time_tree_struct import TTCalendar, TTEvent, TTTime

CONFIG_PATH = os.path.join(os.getcwd(), "config.txt")

DATE_FMT = "%d-%b-%Y %H:%M"


def fetch_calendars(s_id, name_filter=None):
    """
    Perform a TimeTree API request to get the list of all calendars for the logged-in User.
    :param s_id: Session ID for the login.
    :param name_filter: If provided, then filter for only calendars with that name.
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


def plot_calendar(events, start, end):
    """
    Plot the events within a TTCalendar visually.
    :param calendar_tt: TTCalendar object populated with events.
    :param start: Beginning of calendar frame.
    :param end: End of calendar frame.
    :return: None
    """
    # Create dummy date
    titles = [e.title for e in events]
    start_dates = [e.start.as_str() for e in events]
    end_dates = [e.end.as_str() for e in events]

    # Setup the dates and calculate durations
    start_dates = [datestr2num(d) for d in start_dates]
    end_dates = [datestr2num(d) for d in end_dates]

    durations = [(end-start) for start, end in zip(start_dates, end_dates)]

    fig, ax = plt.subplots(figsize=(15, 8), facecolor='#25253c')

    ax.set_facecolor('#25253c')

    # Create colours for each task based on categories
    colors = ['#7a5195', '#ef5675', '#ffa600']
    task_colors = [colors[0]] * 3+[colors[1]] * 4+[colors[2]] * 3

    # Display the bars
    ax.barh(y=titles, width=durations, left=start_dates,
            height=0.8, color=task_colors)

    ax.invert_yaxis()

    # Setup the x axis labels
    ax.set_xlim(start_dates[0], end_dates[-1])

    date_form = DateFormatter("%Y-%m-%d")
    ax.xaxis.set_major_formatter(date_form)

    ax.xaxis.set_major_locator(DayLocator(interval=10))
    ax.xaxis.set_minor_locator(AutoMinorLocator(5))
    ax.tick_params(axis='x', which='minor', length=2, color='white', labelsize=6)

    ax.get_yaxis().set_visible(False)

    # Control the colour of the grid for major and minor lines
    ax.grid(True, axis='x', linestyle='-', color='#FFFFFF', alpha=0.2, which='major')
    ax.grid(True, axis='x', linestyle='-', color='#FFFFFF', alpha=0.05, which='minor')
    ax.set_axisbelow(True)

    # Add labels for each task. For padding, we can use an f-string and add some extra space
    for i, task in enumerate(titles):
        ax.text(start_dates[i], i, f'  {task}', ha='left', va='center', color='white', fontsize=12, fontweight='bold')

    # Add the current date line
    today = dt.datetime.now().strftime("%Y-%m-%d")
    today_num = datestr2num(today)
    ax.axvline(today_num, color='red', alpha=0.8)

    # Style ticks, labels and colours
    ax.tick_params(axis='both', colors='white')

    ax.set_xlabel('Date', color='white', fontsize=12)
    ax.set_title('Project Schedule', color='white', fontsize=14)

    # Hide spines so only bottom is visible
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Create a list of custom patches for the legend
    legend_elements = [
        Patch(facecolor=colors[0], label='Planning'),
        Patch(facecolor=colors[1], label='Development'),
        Patch(facecolor=colors[2], label='Testing'),
    ]

    # Add the legend in the top right corner of the plot
    ax.legend(handles=legend_elements, loc='upper right',
              facecolor='white',
              edgecolor='white',
              fontsize=10, title='Phases', title_fontsize=12, frameon=True)

    plt.show()


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
    # TODO it optional for event_between_dates to round to the whole day when filtering
    relevant_events = calendar.events_between_dates(disp_start, disp_end)

    print(" -- Initialising Loop for Displaying Events --")
    update_count = 0
    # TODO add in some sort of exit feature
    while 1:
        print(f" -- Printing Events between {disp_start.as_dt().strftime(DATE_FMT)} and {disp_end.as_dt().strftime(DATE_FMT)} -- ")
        print(f"Update {update_count}: {dt.datetime.now().strftime('%H:%M:%S')}")
        print_events(relevant_events, calendar.recur_events, calendar.label_data, calendar.known_users)

        # Wait for the required interval before refreshing
        time.sleep(refresh_interval_s)
        calendar.refresh_events()
        relevant_events = calendar.events_between_dates(disp_start, disp_end)
        update_count += 1


def print_events(events: list, recur_events: list, labels: dict, users: dict):
    """
    Print a list of events in chronological order with nice formatting.
    :param events: List of TTEvent objects to be printed.
    :param recur_events: List of all recurring events that could be parents of TTEventRecurs
    :param labels: List of label information.
    :param users: List of author information.
    :return:
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
    print(tabulate.tabulate(entries, headers, tablefmt="simple_outline", colalign=("centre",)))


def main(config_path):
    """
    Test functionality by requesting and printing calendar events.
    :param config_path: Full file path to the config.txt file with login details.
    :return: None
    """
    login_dict = details_from_config(config_path)

    sessionn_id = get_session(login_dict)

    print(f"TimeTree API Session ID is: {sessionn_id}")

    # This line assumes that there is only one calendar called Ruth
    main_calendar = fetch_calendars(sessionn_id, name_filter="Ruth")[0]

    run_live_view(main_calendar, 10)


if __name__ == "__main__":
    main(CONFIG_PATH)


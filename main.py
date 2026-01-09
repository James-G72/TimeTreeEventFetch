"""Run basic commands to access TimeTree data."""
import os
import requests
import datetime as dt
import matplotlib.pyplot as plt
from matplotlib.dates import datestr2num, DateFormatter, DayLocator
from matplotlib.ticker import AutoMinorLocator
from matplotlib.patches import Patch

from utils import details_from_config, get_session, dt_to_milli_since_e, milli_since_e_to_dt
from api_details import API_URL, API_AGENT
from time_tree_struct import TTCalendar, TTTime

CONFIG_PATH = os.path.join(os.getcwd(), "config.txt")

DATE_FMT = "%d-%m-%Y %H:%M"


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


def main(config_path):
    """
    Test functionality by requesting and printing calendar events.
    :param config_path: Full file path to the config.txt file with login details.
    :return: None
    """
    login_dict = details_from_config(config_path)

    sessionn_id = get_session(login_dict)

    print(f"TimeTree API Session ID is: {sessionn_id}")

    calendars = fetch_calendars(sessionn_id, name_filter="Ruth")

    search_end = TTTime(dt_object=dt.datetime.now() + dt.timedelta(weeks=1))
    search_start = TTTime(dt_object=dt.datetime.now() - dt.timedelta(weeks=1000))

    for calendar in calendars:
        calendar.fetch_events(search_start, search_end)

    search_start = TTTime(dt_object=dt.datetime.now()-dt.timedelta(weeks=1))

    for calendar in calendars:
        relevent_events = calendar.events_between_dates(search_start, search_end)

    plot_calendar(relevent_events, search_start, search_end)


if __name__ == "__main__":
    main(CONFIG_PATH)


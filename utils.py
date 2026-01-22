import os
import uuid
import requests
import datetime as dt
from api_details import API_URL, API_AGENT

CONFIG_PATH = os.path.join(os.getcwd(), "config.txt")

def details_from_config(config_path:str):
    """Extract the required username and password from config."""
    login_details = {}
    assert os.path.exists(config_path), FileNotFoundError("You must have a file called config.txt located in this repository."
                                                          "Edit CONFIG_PATH in utils.py to change the default location.")
    with open(config_path) as f:
        for line in f.readlines():
            if "Username" in line:
                login_details["Username"] = line.split(":")[1]
            elif "Password" in line:
                login_details["Password"] = line.split(":")[1]
    # Ensure there are no newline characters at the end
    for key, var in login_details.items():
        if var[-1] == "\n":
            login_details[key] = var[:-1]
    assert "Username" in login_details.keys() and "Password" in login_details.keys()

    return login_details


def get_session(login_details: dict):
    """
    Initialise a session with the TimeTree API using the email login route
    :param login_details: Dictionary of Username and Password
    :return: session_id, A synced session id with the TimeTree server.
    """
    url = f"{API_URL}/auth/email/signin"
    payload = {
        "uid": login_details["Username"],
        "password": login_details["Password"],
        "uuid": str(uuid.uuid4()).replace("-", ""),
    }
    headers = {
        "Content-Type": "application/json",
        "X-Timetreea": API_AGENT,
    }

    response = requests.put(url, json=payload, headers=headers, timeout=10)

    if response.status_code != 200:
        # TODO work out what to actually do if it fails.
        print("Login failed")
    else:
        session_id = response.cookies["_session_id"]
        return session_id

    return None


def dt_to_milli_since_e(datetime_obj: dt.datetime):
    """
    Return the time format used by TimeTree from a datetime object. Milliseconds since Jan 1st 1970.
    :param datetime_obj: Datetime.datetime object for conversion.
    :return: Float of milliseconds since epoch.
    """
    epoch = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)

    return (datetime_obj-epoch).total_seconds() * 1000.0


def milli_since_e_to_dt(ms_since_e: float):
    """
    Return a Datetime.datetime object from milliseconds since Jan 1st 1970.
    :type ms_since_e: floatFloat of milliseconds since epoch.
    :return: Datetime.datetime object.
    """
    # Value is divided by 1000 as the timestamp is assumed in seconds
    return dt.datetime.fromtimestamp(ms_since_e/1000.0)


def sort_events_by_start(event_list:list):
    """
    Sort provided TTEvents by the date they are due to start.
    :param event_list: list of TTEvent objects.
    :return: event_list sorted by the start value of each tt_event object.
    """
    index_list = []
    for i, e in enumerate(event_list):
        index_list.append([e.start.as_ms(), i])

    sorted_list = sorted(index_list)

    return [event_list[x[1]] for x in sorted_list]


def sort_events_by_updated(event_list:list):
    """
    Sort provided TTEvents by the date they were last updated.
    :param event_list: list of TTEvent objects.
    :return: event_list sorted by the updated value of each tt_event object.
    """
    index_list = []
    for i, e in enumerate(event_list):
        index_list.append([e.updated.as_ms(), i])

    sorted_list = sorted(index_list, reverse=True)

    return [event_list[x[1]] for x in sorted_list]
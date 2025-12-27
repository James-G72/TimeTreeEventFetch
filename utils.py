import os
import uuid
import requests
import datetime as dt
from api_details import API_URL, API_AGENT

CONFIG_PATH = os.path.join(os.getcwd(), "config.txt")
DAY_MS = 1000*60*60*24

def details_from_config(config_path):
    """Extract the required username and password from config."""
    login_details = {}
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


def get_session(login_details):
    """
    Initialise a session with the TimeTree API using the email login route
    :param login_details: Dictionary of Username and Password
    :return: session_id, A synced session id with the TimeTree server.
    """
    """
        Log in to the TimeTree app and return the session ID.
        """
    url = f"{API_URL}/auth/email/signin"
    payload = {
        "uid":login_details["Username"],
        "password":login_details["Password"],
        "uuid":str(uuid.uuid4()).replace("-",""),
    }
    headers = {
        "Content-Type":"application/json",
        "X-Timetreea":API_AGENT,
    }

    response = requests.put(url,json=payload,headers=headers,timeout=10)

    if response.status_code != 200:
        print("Login failed")
    try:
        session_id = response.cookies["_session_id"]
        return session_id
    except KeyError:
        return None


def dt_to_milli_since_e(datetime_obj):
    """
    Return the time format used by TimeTree from a datetime object. Milliseconds since Jan 1st 1970.
    :param datetime_obj: Datetime.datetime object for conversion.
    :return: Float of milliseconds since epoch.
    """
    epoch = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)

    return (datetime_obj-epoch).total_seconds() * 1000.0


def milli_since_e_to_dt(epoch_num):
    """
    Return a Datetime.datetime object from milliseconds since Jan 1st 1970.
    :param epoch_num: Float of milliseconds since epoch.
    :return: Datetime.datetime object.
    """
    # Value is divided by 1000 as the timestamp is assumed in seconds
    return dt.datetime.fromtimestamp(epoch_num/1000.0, tz=dt.timezone.utc)



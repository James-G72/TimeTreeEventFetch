"""Defines specific classes for Time Tree data types at different levels"""
import datetime as dt
import requests

from api_details import API_URL, API_AGENT
from utils import DAY_MS


def sort_events_by_start(event_list):
    """
    Sort provided TTEvents by the date they are due to start.
    :param event_list: list of TTEvent objects.
    :return: event_list sorted by the start value of each tt_event object.
    """
    index_list = []
    for i, e in enumerate(event_list):
        index_list.append([e.start, i])

    sorted_list = sorted(index_list)

    return [event_list[x[1]] for x in sorted_list]

def unpack_events(event_list):
    """
    Create TTEvent objects from a list of calendar events.
    :param event_list: List of dictionaries as returned by the TimeTree API.
    :return: List of TTEvent objects for each dictionary.
    """
    tt_events = []
    for event in event_list:
        tt_events.append(TTEvent(event))

    return tt_events


class TTCalendar(object):
    """Calendar Object relating to a single Time Tree calendar."""

    def __init__(self, session_id, response_dict):
        """
        Initialise a calendar instance from a full API response.
        :param session_id: TimeTree API session ID
        :param response_dict: Full response from the API with all calendar information.
        """
        self.events = None
        self.s_id = session_id
        # Unpack the API response to get basic data
        self._extract_useful_info(response_dict)

    def _extract_useful_info(self, resp):
        """
        There is a lot of information from the API. Only retaining the useful data.
        :param resp: TimeTree API response with information about the calendar.
        :return: None
        """
        self.name = resp["name"]
        self.alias = resp["alias_code"]
        self.unique_id = resp["id"]
        self.known_users = dict([[user["user_id"], user["name"]] for user in resp["calendar_users"]])
        self._extract_event_labels(resp["calendar_labels"])

    def _extract_event_labels(self, label_list):
        """
        Extract the relevant information from the included label metadata.
        :param label_list: List of dictionaries with information about each label.
        :return: None
        """
        _temp_labels = {}
        for label in label_list:
            _temp_labels[label["id"]] = {
                "name": label["name"],
                "colour": label["color"],
            }
        self.label_data = _temp_labels

    def _get_events_recur(self, temp_session, since):
        """
        Return events for this calendar created between two dates only.
        :param temp_session: Requests session object with the session_id stored.
        :param since: Start time for the query (interpreted as updated since).
        :return: List of events from the server.
        """
        # Note that the "since" keyword here indicated the event having been updated since that time.
        url = f"{API_URL}/calendar/{self.unique_id}/events/sync?since={since}"
        response = temp_session.get(url,
                                    headers={"Content-Type": "application/json", "X-Timetreea": API_AGENT},
                                    )

        assert response.status_code == 200, print(f"Failed to get events of the calendar {self.name}")
        
        r_json = response.json()

        events = r_json["events"]
        if r_json["chunk"] is True:
            events.extend(self._get_events_recur(temp_session, r_json["since"]))

        return events

    def fetch_events(self, since, until):
        """Request all events relevant to the calendar that start between the given times.
        :param since: Start of event window in milliseconds since epoch
        :param until: End of event window in milliseconds since epoch
        :return: None
        """
        # Create a session in this scope
        _temp_session = requests.Session()
        _temp_session.cookies.set("_session_id", self.s_id)

        url = f"{API_URL}/calendar/{self.unique_id}/events/sync"
        response = _temp_session.get(
            url,
            headers={"Content-Type": "application/json", "X-Timetreea": API_AGENT},
        )
        assert response.status_code == 200, print(f"Failed to get events of the calendar {self.name}")

        r_json = response.json()
        events = r_json["events"]
        if r_json["chunk"] is True:
            events.extend(self._get_events_recur(_temp_session, r_json["since"]))

        events_tt = unpack_events(events)

        sorted_events_tt = sort_events_by_start(events_tt)

        self.events = []
        for tt_event in sorted_events_tt:
            if since <= tt_event.start <= until:
                self.events.append(tt_event)


class TTEvent(object):
    """Event Object that relates to a single event, within a TTCalendar."""

    def __init__(self, event_dict):
        """Init"""
        self.parent_id = event_dict["calendar_id"]

        self._extract_useful_info(event_dict)

    def _extract_useful_info(self, full_dictionary):
        """To reduce the size of the object, only take relevant information."""
        self.id = full_dictionary["id"]
        self.author_id = full_dictionary["author_id"]
        self.title = full_dictionary["title"]
        self.start = full_dictionary["start_at"]
        # All Day events are considered to end on a day, but last for all of it. A day worth of milliseconds therefore needs to be added.
        if full_dictionary["all_day"]:
            self.end = full_dictionary["end_at"] + DAY_MS
        else:
            self.end = full_dictionary["end_at"]
        self.start = full_dictionary["start_at"]
        self.label_id = full_dictionary["label_id"]

"""Defines specific classes for Time Tree data types at different levels"""
import datetime as dt
import requests

from api_details import API_URL, API_AGENT


class TTCalendar(object):
    """Calendar Object relating to a single Time Tree calendar."""

    def __init__(self, session_id, response_dict):
        """
        Initialise a calendar instance from a full API response.
        :param session_id: TimeTree API session ID
        :param response_dict: Full response from the API with all calendar information.
        """
        self.s_id = session_id
        # Unpack the API response to get basic data
        self._extract_useful_info(response_dict)

    def _extract_useful_info(self, resp):
        """There is a lot of information from the API. Only retaining the useful data."""
        self.name = resp["name"]
        self.alias = resp["alias_code"]
        self.unique_id = resp["id"]
        self.known_users = [user["name"] for user in resp["calendar_users"]]
        self.label_data = self._extract_event_labels(resp["calendar_labels"])

    def _extract_event_labels(self, label_list):
        """Extract the relevant information from the included label metadata.
        This information can then be related to the event labels for this calendar."""
        _temp_labels = {}
        for label in label_list:
            _temp_labels[label["id"]] = {
                "name": label["name"],
                "colour": label["color"],
            }
        return _temp_labels

    def _get_events_recur(self, temp_session, since, until):
        """
        Return events for this calendar between two dates only.
        """
        # Note that the "since" keyword here indicated the event having been updated since that time.
        url = f"{API_URL}/calendar/{self.unique_id}/events/sync?since={since}"
        response = temp_session.get(
            url,
            headers={"Content-Type": "application/json", "X-Timetreea": API_AGENT},
        )

        assert response.status_code == 200, print(f"Failed to get events of the calendar {self.name}")

        r_json = response.json()

        events = r_json["events"]
        if r_json["chunk"] is True:
            events.extend(self._get_events_recur(temp_session, r_json["since"], until))

        return events

    def _unpack_events(self, event_list):
        """Create TTEvent object from a list of calendar events."""
        tt_events = []
        for event in event_list:
            tt_events.append(TTEvent(event))

        return tt_events

    def fetch_events(self, since, until):
        """Request all events relevant to the calendar between the given times."""
        # Create a session in this scope
        _temp_session = requests.Session()
        _temp_session.cookies.set("_session_id", self.s_id)

        events = self._get_events_recur(_temp_session, since, until)

        events_as_tt_event = self._unpack_events(events)

        for tt_event in events_as_tt_event:
            t = 1

        self.events = events_as_tt_event

        return events_as_tt_event


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
        self.end = full_dictionary["end_at"]
        self.label_id = full_dictionary["label_id"]

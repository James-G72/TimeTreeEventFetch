"""Defines specific classes for Time Tree data types at different levels"""


class TTCalendar(object):
    """Calendar Object relating to a single Time Tree calendar."""

    def __init__(self, session, response_dict):
        """
        Initialise a calendar instance from a full API response.
        :param session: TimeTree API session ID
        :param response_dict: Full response from the API with all calendar information.
        """
        self.s_id = session
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

    def fetch_events(self):
        """Request all events relevant to the calendar."""
        t = 1
        # TODO implement event fetching




class TTEvent(object):
    """Event Object that relates to a single event, within a TTCalendar."""

    def __init__(self, something):
        """Init"""
        self.something = something


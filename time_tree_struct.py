"""Defines specific classes for Time Tree data types at different levels"""
import datetime as dt
from dateutil.relativedelta import relativedelta
import pytz
import requests
import re

from api_details import API_URL, API_AGENT
from utils import DAY_MS, dt_to_milli_since_e, milli_since_e_to_dt

EXCEPTION_DATE_FMT = "%Y%m%dT%H%M%SZ"
PRINT_DATE_FMT = "%d-%m-%Y %H:%M"
UNTIL_DATE_FMT = "%Y%m%d"
FULL_RULE_LIST = ["FREQ", "INTERVAL", "WKST", "BYDAY", "UNTIL"]
RECUR_GAPS = {
    "WEEKLY": relativedelta(weeks=+1),
    "DAILY": relativedelta(days=+1),
    "MONTHLY": relativedelta(months=+1),
    "YEARLY": relativedelta(years=+1)
}


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
        self.bounds = None
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
        :param since: Datetime object for the start
        :param until: Datetime object for the end
        :return: None
        """
        since_mse = dt_to_milli_since_e(since)
        until_mse = dt_to_milli_since_e(until)
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
            if since_mse <= tt_event.start <= until_mse:
                self.events.append(tt_event)

        self.bounds = [since, until]

    def events_between_dates(self, start_date, end_date):
        """
        Return all events, including recurring events, that occur in the datetime window provided.
        Recurring events are returned as TTEventRecurence objects
        :param start_date: datetime object for the start of the window
        :param end_date: datetime object for the start of the window
        :return:
        """
        matching_events = []
        start_mse = dt_to_milli_since_e(start_date)
        end_mse = dt_to_milli_since_e(end_date)
        # Getting all standard events
        for e in self.events:
            if start_mse <= e.start <= end_mse:
                matching_events.append(e)
            if e.recurs:
                _r_events = e.recur_within_dates(start_date, end_date)
                if len(_r_events) > 0:
                    matching_events.extend(_r_events)

        return matching_events


class TTEvent(object):
    """Event Object that relates to a single event, within a TTCalendar."""

    def __init__(self, event_dict):
        """Init"""
        self.parent_id = event_dict["calendar_id"]
        self.recurs = False

        self._extract_useful_info(event_dict)

    def _extract_useful_info(self, full_dictionary):
        """To reduce the size of the object, only take relevant information."""
        self.id = full_dictionary["id"]
        self.author_id = full_dictionary["author_id"]
        self.title = full_dictionary["title"]
        self.updated = full_dictionary["updated_at"]
        self.start = full_dictionary["start_at"]
        # All Day events are considered to end on a day, but last for all of it.
        # A day worth of milliseconds therefore needs to be added.
        if full_dictionary["all_day"]:
            self.end = full_dictionary["end_at"] + DAY_MS
        else:
            self.end = full_dictionary["end_at"]
        self.duration = self.end - self.start
        self.label_id = full_dictionary["label_id"]
        if len(full_dictionary["recurrences"]) > 0:
            self._store_recurance(full_dictionary["recurrences"])

    def _unpack_rules(self, rule_list):
        """Unpack all rules from the list."""
        _tmp_rule_dict = {}
        for rule in FULL_RULE_LIST:
            if rule in rule_list:
                _tmp_rule_dict[rule] = rule_list.split(rule)[1].split("=")[1].split(";")[0]

        self.recur_rules = _tmp_rule_dict

    def _store_recurance(self, rule_list):
        exceptions = [x.split("EXDATE:")[1] for x in rule_list[1:]]
        exceptions_dt = [dt.datetime.strptime(exp, EXCEPTION_DATE_FMT) for exp in exceptions]
        for idx, exp_dt in enumerate(exceptions_dt):
            exceptions_dt[idx] = pytz.utc.localize(exp_dt)

        self._unpack_rules(rule_list[0])

        if len(exceptions_dt) > 0:
            self.recur_rules["EXDATE"] = [dt_to_milli_since_e(exp_dt) for exp_dt in exceptions_dt]
            self.recur_exceptions = 1

        self.recurs = True

    def _handle_until_fmt(self, date):
        """The until recurrence flag seems to have inconsistent formatting."""
        for try_fmt in [EXCEPTION_DATE_FMT, UNTIL_DATE_FMT]:
            try:
                dt_obj = dt.datetime.strptime(date, try_fmt)
                return pytz.utc.localize(dt_obj)
            except:
                pass
        return None

    def recur_within_dates(self, start_date, end_date):
        """
        Return all instances of the event that occur within a time frame.
        :param start_date: datetime object of start
        :param end_date: datetime object of end
        :return: All recur instances in that span.
        """
        self_start = milli_since_e_to_dt(self.start)

        # Preventing the function from wasting time and memory calculating recurrences
        if "UNTIL" in self.recur_rules.keys():
            recur_finish_date = self._handle_until_fmt(self.recur_rules["UNTIL"])
            if recur_finish_date < start_date:
                return []
        if self_start > end_date:
            return []

        # Getting exception dates if they're there
        if "EXDATE" in self.recur_rules.keys():
            exceptions = self.recur_rules["EXDATE"]
        else:
            exceptions = []

        latest_event_time = self_start
        recur_gap = RECUR_GAPS[self.recur_rules["FREQ"]]
        if "INTERVAL" in self.recur_rules.keys():
            interval = int(self.recur_rules["INTERVAL"])
        else:
            # I have only seen interval not used in the context where it is a weekly recurring event
            interval = 1
        instances = []
        print(f"Processing {self.title}")
        while latest_event_time < end_date:
            latest_event_time += recur_gap * interval
            if start_date <= latest_event_time <= end_date:
                if dt_to_milli_since_e(latest_event_time) not in exceptions:
                    _latest_end = latest_event_time + dt.timedelta(milliseconds=self.duration)
                instances.append(TTEventRecur(self, latest_event_time, _latest_end))
            if dt_to_milli_since_e(latest_event_time) in exceptions:
                curr_date_mse = dt_to_milli_since_e(latest_event_time)
                t = 1

        return instances


# I am unsure at this stage if this is the best way to implement this
class TTEventRecur(object):
    """Event Object that relates to a single occurrence of a TTEvent. A TTEventRecur must have a parent TTEvent object."""

    def __init__(self, parent_event, instance_start, instance_end):
        """Initialise from the parent TTEvent."""
        self.parent_id = parent_event.id
        self.start = dt_to_milli_since_e(instance_start)
        self.end = dt_to_milli_since_e(instance_end)
        self.title = parent_event.title
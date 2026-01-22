"""Defines specific classes for Time Tree data types at different levels"""
import datetime as dt
from dateutil.relativedelta import relativedelta
import pytz
import requests
import uuid

from api_details import API_URL, API_AGENT
from utils import dt_to_milli_since_e, milli_since_e_to_dt, sort_events_by_updated, sort_events_by_start, get_session

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
DAY_MS = 1000*60*60*24


# TODO add the operator functionality such that the TTTime objects can be used directly with datetime objects and compared
class TTTime(object):
    """A custom time object that prevents the need to convert from datetime to milliseconds since epoch."""

    def __init__(self, dt_object:dt.datetime=None, ms_since_e:float=None):
        """
        Initialise with either a milliseconds since epoch or a datetime object. Datetime object takes priority.
        :param dt_object: datetime object as input.
        :param ms_since_e: float of milliseconds since epoch.
        """
        if dt_object:
            _time = dt_object
        elif ms_since_e:
            _time = milli_since_e_to_dt(ms_since_e)
        else: raise Exception("Neither dt_object not ms_since_e passed when initialising TTTIme object.")

        if not _time.tzinfo:
            self.time = pytz.utc.localize(_time)
        else:
            self.time = _time

    def as_ms(self):
        """Return the time as milliseconds since epoch."""
        return dt_to_milli_since_e(self.time)

    def as_dt(self):
        """Return the time as a datetime object."""
        return self.time

    def as_str(self):
        """Return the time as a string."""
        return self.time.strftime(EXCEPTION_DATE_FMT)

    def apply_delta(self, duration:relativedelta, repeats:int=1):
        """
        Use relativedelta objects to modify the time
        :param duration: relative delta object with a signed delta application.
        :param repeats: integer value that allows for multiple applications of the delta
        :return: None
        """
        self.time += duration * repeats


def round_tttime_to_day(ttt_obj:TTTime, up: bool =False):
    """
    Round a TTTime object to the nearest day and return as a datetime
    :param ttt_obj: TTTime object to be rounded
    :param up: If True, then round up a day
    :return: Datetime object
    """
    if up:
        _dt_plus_day = ttt_obj.as_dt() + dt.timedelta(days=1)
    day_only = ttt_obj.as_dt().strftime("%Y%m%d")

    return TTTime(dt_object=dt.datetime.strptime(day_only, "%Y%m%d"))


class TTEvent(object):
    """Event Object that relates to a single event, within a TTCalendar."""

    def __init__(self, event_dict:dict):
        """Init"""
        self.parent_id = event_dict["calendar_id"]
        self.recurs = False
        self.deleted = False
        self.deleted_date = None

        self._extract_useful_info(event_dict)

    def _extract_useful_info(self, full_dictionary:dict):
        """To reduce the size of the object, only take relevant information."""
        self.id = full_dictionary["id"]
        self.author_id = full_dictionary["author_id"]
        self.title = full_dictionary["title"]
        self.updated = TTTime(ms_since_e=full_dictionary["updated_at"])
        self.start = TTTime(ms_since_e=full_dictionary["start_at"])
        # All Day events are considered to end on a day, but last for all of it.
        # A day worth of milliseconds therefore needs to be added.
        if full_dictionary["all_day"]:
            self.end = TTTime(ms_since_e=full_dictionary["end_at"] + DAY_MS - 1000)
        else:
            self.end = TTTime(ms_since_e=full_dictionary["end_at"])
        self.duration = self.end.as_ms() - self.start.as_ms()
        self.label_id = full_dictionary["label_id"]
        if len(full_dictionary["recurrences"]) > 0:
            self._store_recurance(full_dictionary["recurrences"])

    def _unpack_rules(self, rule_list:str):
        """
        Unpack all rules from the list.
        :param rule_list: string of all rules separated by a colon
        :return: None
        """
        _tmp_rule_dict = {}
        for rule in FULL_RULE_LIST:
            if rule in rule_list:
                _tmp_rule_dict[rule] = rule_list.split(rule)[1].split("=")[1].split(";")[0]

        self.recur_rules = _tmp_rule_dict

    def _store_recurance(self, rule_list:str):
        """
        Store all relevant information about recurrences.
        :param rule_list: string with a list of all rules
        :return: None
        """
        exceptions = [x.split("EXDATE:")[1] for x in rule_list[1:]]
        exceptions_dt = [TTTime(dt_object=dt.datetime.strptime(exp, EXCEPTION_DATE_FMT)) for exp in exceptions]

        self._unpack_rules(rule_list[0])

        if len(exceptions_dt) > 0:
            self.recur_rules["EXDATE"] = exceptions_dt
            self.recur_exceptions = 1

        self.recurs = True

    def _handle_until_fmt(self, date:str):
        """The until recurrence flag seems to have inconsistent formatting."""
        for try_fmt in [EXCEPTION_DATE_FMT, UNTIL_DATE_FMT]:
            try:
                dt_obj = dt.datetime.strptime(date, try_fmt)
                return TTTime(dt_object=dt_obj)
            except:
                pass
        return None

    def recur_within_dates(self, start_date:TTTime, end_date:TTTime):
        """
        Return all instances of the event that occur within a time frame.
        :param start_date: TTTime object of start
        :param end_date: TTTime object of end
        :return: All recur instances in that span.
        """
        # Preventing the function from wasting time and memory calculating recurrences
        if "UNTIL" in self.recur_rules.keys():
            recur_finish_date = self._handle_until_fmt(self.recur_rules["UNTIL"])
            if recur_finish_date.as_dt() < start_date.as_dt():
                return []
        if self.start.as_dt() > end_date.as_dt():
            return []

        # Getting exception dates if they're there
        if "EXDATE" in self.recur_rules.keys():
            exceptions = [x.as_ms() for x in self.recur_rules["EXDATE"]]
        else:
            exceptions = []

        latest_event_time = self.start
        recur_gap = RECUR_GAPS[self.recur_rules["FREQ"]]
        if "INTERVAL" in self.recur_rules.keys():
            interval = int(self.recur_rules["INTERVAL"])
        else:
            # I have only seen interval not used in the context where it is a weekly recurring event
            interval = 1

        instances = []
        while latest_event_time.as_dt() < end_date.as_dt():
            if start_date.as_dt() <= latest_event_time.as_dt() <= end_date.as_dt():
                if latest_event_time.as_ms() not in exceptions:
                    _latest_end = latest_event_time.as_dt() + dt.timedelta(milliseconds=self.duration)
                    # start time is explicitly set as a new TTTime object to stop the update to latest_event_time below from changing the value
                    instances.append(TTEventRecur(self, TTTime(dt_object=latest_event_time.as_dt()), TTTime(dt_object=_latest_end)))
            latest_event_time.apply_delta(recur_gap, interval)

        return instances


class TTEventRecur(object):
    """Event Object that relates to a single occurrence of a TTEvent. A TTEventRecur must have a parent TTEvent object."""

    def __init__(self, parent_event:TTEvent, instance_start:TTTime, instance_end:TTTime):
        """Initialise from the parent TTEvent."""
        self.parent_id = parent_event.id
        self.start = instance_start
        self.end = instance_end
        self.title = parent_event.title


class TTCalendar(object):
    """Calendar Object relating to a single Time Tree calendar."""

    def __init__(self, session_id:str, response_dict:dict, login: dict):
        """
        Initialise a calendar instance from a full API response.
        :param session_id: TimeTree API session ID
        :param response_dict: Full response from the API with all calendar information.
        :param login: Dictionary of login details. Allows session ID to be refreshed.
        """
        self.events = None
        self.recur_events = None
        self.bounds = None
        self.deleted_events = None
        self.s_id = session_id
        self.login_info = login
        # Unpack the API response to get basic data
        self._extract_useful_info(response_dict)

    def _refresh_session(self):
        """
        Obtain a new session id if ever a request fails.
        :return: None
        """
        self.s_id = get_session(self.login_info)

    def _extract_useful_info(self, resp:dict):
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
        self.created = TTTime(ms_since_e=resp["created_at"])

    def _extract_event_labels(self, label_list:list):
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

    def _contact_api(self, session:requests.session, url:str):
        """
        Get an individual response from the TimeTree API.
        :param session: requests session object to be queried
        :param url: Later part of he url to hit at the API
        :return: full response from the API in json
        """
        # TODO add some sort of handling for an expired session token. Currently unsure what to expect.
        tries = 0
        while tries < 3:
            response = session.get(url,
                                   headers={"Content-Type": "application/json", "X-Timetreea": API_AGENT},
                                   )
            if response.status_code != 200:
                print(f"Failed to get events of the calendar {self.name}")
                # Assuming an expired session could be an issue
                self._refresh_session()
            else:
                return response.json()
            tries += 1
        print(f"Could not get a valid response from the API after {tries} tries.")

        return None

    def _get_events_recur(self, temp_session:requests.session, since:TTTime):
        """
        Return events for this calendar created between two dates only.
        :param temp_session: Requests session object with the session_id stored.
        :param since: TTTime for start time for the query (interpreted as updated since).
        :return: List of events from the server.
        """
        # Note that the "since" keyword here indicated the event having been updated since that time.
        url = f"{API_URL}/calendar/{self.unique_id}/events/sync?since={since.as_ms()}"
        r_json = self._contact_api(temp_session, url)

        events = r_json["events"]
        if r_json["chunk"] is True:
            since_time = TTTime(ms_since_e=r_json["since"])
            events.extend(self._get_events_recur(temp_session, since_time))

        return events

    def _update_deleted(self, updated_events: list):
        """
        Given a new sync, identify if any events have been deleted. We should only enter this function if self.events
        has TTEvents already populated.
        :param updated_events: list of TTEvent object that are
        :return: None
        """
        new_id_list = [e.id for e in updated_events]
        missing_list = []
        for e in self.events:
            if e.id not in new_id_list:
                e.deleted = True
                e.deleted_time = TTTime(dt_object=dt.datetime.now())
                missing_list.append(e)
        if len(missing_list) > 0:
            if not self.deleted_events:
                self.deleted_events = missing_list
            else:
                self.deleted_events.extend(missing_list)

    def fetch_events(self, since:TTTime=None, until:TTTime=None):
        """Request all events relevant to the calendar that start between the given times.
        :param since: TTTime object for the start
        :param until: TTTime object for the end
        :return: None
        """
        if not until:
            # Setting the end date to an infeasibly distant date
            until = TTTime(dt_object=dt.datetime.now()+dt.timedelta(weeks=1000))
        if not since:
            since = TTTime(self.created.as_dt() - dt.timedelta(weeks=52))
        # Create a session in this scope
        _temp_session = requests.Session()
        _temp_session.cookies.set("_session_id", self.s_id)

        url = f"{API_URL}/calendar/{self.unique_id}/events/sync"
        r_json = self._contact_api(_temp_session, url)

        events = r_json["events"]
        if r_json["chunk"] is True:
            since_time = TTTime(ms_since_e=r_json["since"])
            events.extend(self._get_events_recur(_temp_session, since_time))

        events_tt = unpack_events(events)

        sorted_events_tt = sort_events_by_start(events_tt)

        if self.events is not None:
            self._update_deleted(sorted_events_tt)

        self.events = []
        self.recur_events = []
        for tt_event in sorted_events_tt:
            if since.as_dt() <= tt_event.start.as_dt() <= until.as_dt():
                if tt_event.recurs:
                    self.recur_events.append(tt_event)
                else:
                    self.events.append(tt_event)

        self.bounds = [since, until]

    def events_between_dates(self, start_date:TTTime, end_date:TTTime, full_day:bool=False):
        """
        Return all events, including recurring events, that occur in the datetime window provided.
        Recurring events are returned as TTEventRecurence objects
        :param start_date: datetime object for the start of the window
        :param end_date: datetime object for the start of the window
        :param full_day: If true then the search window is rounded to the nearest days
        :return: All TTEvent objects in the window.
        """
        if full_day:
            start_date = round_tttime_to_day(start_date, up=False)
            end_date = round_tttime_to_day(end_date, up=True)
        matching_events = []
        # Getting all standard events
        for e in self.events:
            if start_date.as_dt() <= e.start.as_dt() <= end_date.as_dt():
                matching_events.append(e)

        for r_e in self.recur_events:
            _r_events = r_e.recur_within_dates(start_date, end_date)
            if len(_r_events) > 0:
                matching_events.extend(_r_events)

        return matching_events

    def _new_event(self, new_event:TTEvent):
        """
        If an event has been created or updated, it needs to be replaced by id or appended if new.
        :param new_event: A new TTEvent object.
        :return: None
        """
        # Check for the ID in the events
        for idx, e in enumerate(self.events):
            if e.id == new_event.id:
                self.events[idx] = new_event
                return

        # Check for the ID in the recurring events
        for idx, r_e in enumerate(self.recur_events):
            if r_e.id == new_event.id:
                self.recur_events[idx] = new_event
                return

        # If we've got to here then it's a new event
        if new_event.recurs:
            self.recur_events.append(new_event)
        else:
            self.events.append(new_event)

    def refresh_events(self):
        """Looks to the API for updates to the events"""
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
        events_tt = unpack_events(events)
        new_sorted_events_tt = sort_events_by_updated(events_tt)
        curr_sorted_events_tt = sort_events_by_updated(self.events)

        updated_events = []
        last_updated_time = curr_sorted_events_tt[0].updated
        # Check if any new events have been edited more recently
        for event_tt in new_sorted_events_tt:
            if event_tt.updated.as_ms() > last_updated_time.as_ms():
                updated_events.append(event_tt)
            else:
                break

        for e in updated_events:
            self._new_event(e)


def unpack_events(event_list:list):
    """
    Create TTEvent objects from a list of calendar events.
    :param event_list: List of dictionaries as returned by the TimeTree API.
    :return: List of TTEvent objects for each dictionary.
    """
    tt_events = []
    for event in event_list:
        tt_events.append(TTEvent(event))

    return tt_events
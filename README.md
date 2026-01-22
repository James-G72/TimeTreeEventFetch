# Time Tree Event Fetch
When looking for ways to interact with the TimeTree calendar app through an API, I found that there was once a supported API that was terminated in 2023: https://timetreeapp.com/intl/en/newsroom/2023-12-14/connect-app-api-202312.

Fortunately there is a Web App for the calendar that you can log into and view and edit all events: https://timetreeapp.com/signin.
This Web App uses an undocumented API that is located at: "https://timetreeapp.com/api/v1". This API seems to have less functionality than the deprecated one mentioned above. It does however allow full access to all calendars and events visible to an account.

## Brief API Overview
The functionality of the API used in this repository is briefly described below.
 - /auth/email/signin
	 - Providing a uid (email) and password at this address will request authorisation for a session.
	 - A successful login will yield a session ID token.
 - /calendars
	 - Hitting this endpoint will return a calendar structure for each calendar available to the logged in user.
	 - A "?since" optional argument can be passed to restrict only to calendars "updated" after the since date (provided in milliseconds since epoch)
	 - An update to a calendar only counts as an update to the calendar details, not any of the events within.
 - /calendar/{calendar ID}/events/sync
	 - Once a calendar ID has been obtained, all events can be synced.
	 - This is designed to be a recurring feature with with the "chunk" flag in the json response indicating if not all events were sent.
	 - Events are returned in order of update.

## Repository Overview
The functionality in this repository is designed to be used in the following way:

 - An initial login is required to get a session ID
 - An initial calendar fetch is required to understand what calendars are available.
	 - TTCalendars are then initialised from this fetch
 - TTCalendars then are able to handle all of the events relevant to that calendar.

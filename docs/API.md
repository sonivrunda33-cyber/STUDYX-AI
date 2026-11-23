# JSON API reference

All endpoints below use `/api`. Except for sign-in and public pages, API routes require an authenticated account. Send the CSRF token from the page's `<meta name="csrf-token">` in the `X-CSRF-Token` header for every write request. JSON responses are scoped to the signed-in user.

| Area | Routes |
|---|---|
| Overview and saved progress | `GET /dashboard`, `GET /progress`, `GET /analytics` |
| Theme preferences | `GET /preferences`, `PATCH /preferences` |
| Courses | `GET /subjects`, `POST /subjects`, `PATCH /subjects/<id>`, `DELETE /subjects/<id>` |
| Assignments | `GET /assignments`, `POST /assignments`, `PATCH /assignments/<id>`, `DELETE /assignments/<id>` |
| Exams | `GET /exams`, `POST /exams`, `PATCH /exams/<id>`, `DELETE /exams/<id>` |
| Calendar | `GET /calendar-events?start=<ISO>&end=<ISO>`, `POST /calendar-events`, `PATCH /calendar-events/<id>`, `DELETE /calendar-events/<id>` |
| Study time | `GET /focus-sessions`, `POST /focus-sessions`, `POST /study-sessions` |
| Smart timetable | `POST /timetable/generate` |
| Usage | `POST /usage-events` |

Write endpoints validate lengths, ranges and user ownership before committing. Calendar time values are ISO-8601 timestamps. The server stores timestamps in UTC and returns UTC ISO-8601 values. Timer and manual-session writes create a study-history record and a linked calendar event together. These endpoints are used by the eight pages in the workspace navigation.

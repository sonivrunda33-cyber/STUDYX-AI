# Student study-planner validation plan

## What is verified so far

The included automated suite currently has checks for SQLite initialization, account registration/login and password hashing, calendar persistence across app startup, focus/manual session storage, timezone-aware analytics, page rendering, CSRF rejection and separation between student accounts. A separate Node-based UI test exercises timer start, pause, resume, early finish and automatic completion. These are engineering checks with synthetic test inputs. They are not a survey and do not count as real participant results.

The project brief asks for feedback from real students. No participant interviews, survey responses or usability results are included here. Collect those before writing outcome claims in the college report.

## Research question and hypotheses

**Research question:** Does one connected student planner help students complete common planning actions with fewer errors and less effort than the method they currently use?

For a within-participant comparison, ask each participant to complete the same short scenarios once with their current method and once in StudyX. Randomize which method they try first. Write down the chosen task and success criteria before testing.

- **H0:** The median completion time for the selected planning scenario is the same with the student's current method and StudyX.
- **H1:** The median completion time is lower with StudyX.
- Use the same task instructions and measures in both conditions. If time differences are skewed or the sample is small, consider a Wilcoxon signed-rank test; if paired-difference assumptions are reasonable, a paired t-test is an option. Report the difference, an interval estimate and an effect size along with the p-value.
- For completion/failure categories, compare proportions and state the test and assumptions. Use descriptive statistics and confidence intervals for ratings and time. A correlation can explore whether the number of saved steps is associated with satisfaction, but it does not show causation.

## Participant plan

- Recruit at least 30 students for the short questionnaire if feasible; describe the actual recruitment method and who was not reached. A convenience sample from one class is not representative of all students.
- Test the working prototype with at least 10 students. Ask for consent, do not collect passwords, and use participant codes instead of names in notes.
- Interview at least five students about their current schedule, course workload and how they make time for exam preparation. Ask about actual recent examples, not only what they think they might do.
- Explain that participants can stop at any time. Keep contact details separate from response data and follow the college's consent and data-storage rules.

## Questionnaire draft

Adapt the wording with your instructor before distributing it. Do not ask for passwords, grades or other unnecessary personal information.

1. **Multiple choice:** What do you currently use most to track courses, assignments and exams? Paper planner / calendar app / course portal / messaging reminders / memory / other.
2. **Numeric:** In a typical week, about how many assignments or study tasks do you track?
3. **Likert, 1–5:** How easy is it to see what you need to study next?
4. **Likert, 1–5:** How confident are you that you will remember an upcoming deadline?
5. **Numeric:** About how many minutes per week do you spend organizing study tasks?
6. **Multiple choice:** Which part is hardest? Prioritizing tasks / remembering deadlines / finding study time / planning around exams / tracking progress / other.
7. **Open response:** Tell us about the last time a study task was forgotten, delayed or hard to plan.
8. **Open response:** What would make a study planner feel useful and realistic to you?

Record the population, sample size, recruitment method, date, missing responses and known limitations before interpreting the survey.

## Prototype task scenarios

Give each participant the same fictional scenario and ask them to use their own account or a designated test account:

1. Add a course and a dated assignment; check that the due date appears on the calendar.
2. Add an exam date and locate it on the calendar.
3. Set a custom focus duration, pause, resume and finish early; confirm that the actual focused time appears in session history and the calendar.
4. Add a manual study session and find it on the progress page.
5. Generate a smart timetable from saved assignments/exams and save a selected block to the calendar.

For each task, record completion (yes/no), time from task start to success, wrong turns/errors, clicks or taps, and a short participant comment. Ask the participant to complete the standard System Usability Scale questionnaire if that is part of the approved course protocol. Keep the original questionnaire and scoring method with the report.

## Built-in measures

The `usage_events` table records page views, control clicks, time on a page, UI errors, completed assignments, focus sessions, manual session entries and calendar-event saves. Each event is account-scoped. The browser does not send field contents, passwords or course content to this measurement table. The app does not currently provide an export/report screen for this table; an authorized project team can aggregate it from the SQLite database for the study report.

Use the participant observation sheet alongside these events. For comparison between a current method and StudyX, record both conditions with the same definitions; the app can only log activity inside the prototype.

## Reporting template

Fill this from the actual collected data:

- Participants invited / completed: `___ / ___`
- Recruitment and sampling method: `___`
- Most frequent planning difficulty: `___`
- Task completion in current method vs StudyX: `___ / ___`
- Median completion time and spread in both conditions: `___ / ___`
- Paired difference, interval estimate, selected test, statistic and p-value: `___`
- Effect size and plain-language meaning: `___`
- SUS score and number of complete forms: `___`
- Assumptions checked and action if they did not hold: `___`
- Limits, possible bias and what the results cannot establish: `___`
- At least three improvement opportunities from observed feedback: `___`

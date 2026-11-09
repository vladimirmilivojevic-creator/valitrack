# A ten-minute walkthrough

All data is invented. Every demo account uses the same password, shown on the login page, and the data is reset every night.

## The people

| Sign in as | Role | What they can do |
|---|---|---|
| Sophie Gruber | Validation engineer | Write requirements, tests and reports. Coordinate changes. Work support tickets. Plan training |
| Lukas Hofer | Tester | Execute tests and upload evidence |
| Eva Mayr | QA manager | Review runs, approve tests, reports and changes, release, close deviations |
| Nina Haas | System owner | Second signature on high-risk changes |
| Tim Steiner | IT administrator | Users, tickets, configuration |
| Paul Keller | Auditor | Read only |

## The story: DocuControl 3.2 to 3.3

DocuControl is a (fictional) document management system with an approved set of requirements. Version 3.2 is live.
A change request moves it to 3.3.

1. **Dashboard** (Sophie). Every application with a lifecycle bar. DocuControl is in *Testing*.
2. **Application, Overview.** The release gate for version 3.3 lists eight checks in plain words. Five are open:
   the PQ test has not passed yet, not every test was executed, a high-risk test waits for QA review, a deviation is open, and no report is approved.
3. **Executions.** One run failed. Open it: step 3 is red, the evidence file has a SHA-256, and the run says that deviation **DEV-0001** was opened by the failure.
4. **Change control, CR-0001.** The timeline shows where the change is. The impact assessment lists the departments with
   their answers and who gave them. The signature block shows who approved and with which meaning.
5. **Traceability.** Requirements down the side, tests across the top, the latest result in each cell. Hatched rows would be gaps.
6. **Deviations.** Open DEV-0001 and write a root cause and a corrective action as Sophie, then mark it resolved.
   Sophie cannot close it: sign out, click Eva Mayr, and close it with a signature.
7. **Finish the testing.** As Lukas, run the failed test again and run the tests that have not been executed. As Eva, review the runs.
   As Sophie, complete testing and generate the validation report (PDF). As Eva, approve the report and release version 3.3.
   After the release, *Training* shows who must be trained on the new version.
8. **Audit trail.** Every step above is in it. Press *Verify integrity*.
9. **SQL reports.** Pick *Traceability* and press *Show SQL*: the report is a view in the database. Download the CSV.

## Things worth trying

- Sign with a wrong password. The signature is refused and counted towards the lockout.
- Edit an approved requirement (Sophie). The release gate says that the requirements changed after approval.
- Try to approve a change that you requested, or a test case that you wrote. The system refuses and says why.
- Change a setting under *Configuration* of a validated application. It needs an approved change request.
- Open the API documentation at `/api/docs`.

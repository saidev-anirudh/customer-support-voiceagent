# Data model

The agent uses one Google spreadsheet with two tabs. **Customers** is read during verification and claim lookups. **Interactions** is appended to when a call ends. Keeping them as separate tabs mirrors two separate systems, a customer and claims system and a call log, and either can be replaced independently (see [configuration.md](configuration.md#swapping-providers)).

## Customers tab (read)

Header names are matched case-insensitively and ignoring punctuation, so `Claim ID`, `claim_id`, and `claim id` are equivalent.

| Column | Meaning |
| --- | --- |
| `Phone` | Account phone number. Matched on the last 10 digits, so formatting and country code do not matter |
| `Name` | Account holder. Only the first name is spoken before verification completes |
| `PIN` | Verification PIN. Compared as digits |
| `Claim ID` | Claim reference, read out digit by digit |
| `Claim Status` | Short status, for example `Approved`, `Under review`, `Pending documents` |
| `Status Detail` | One sentence of context the agent may state |
| `Documents Needed` | `TRUE` or `FALSE` |
| `Document Instructions` | Steps for submitting documents. Spoken only when `Documents Needed` is `TRUE` |
| `Preferred Language` | `en` or `hi`. Stored for reference |

Notes:

- Keep the sheet's Phone and PIN columns formatted as plain text so leading zeros survive. The agent reads them as text.
- The agent states only what is in these columns. It does not invent dates, amounts, or promises.
- PINs are stored in plain text here to keep the sample simple. For production, store a salted hash and verify against it. See [deployment.md](deployment.md#production-hardening).

## Interactions tab (write)

One row is appended per call. The agent reads the header row and writes each value under its matching header, so you can reorder columns or add your own. Unknown headers are left blank.

| Column | Meaning |
| --- | --- |
| `Timestamp` | UTC time the record was written, ISO 8601 |
| `Caller Name` | Account holder name. Marked `(unverified)` if an account was found but the PIN failed. `Unknown` if no account was found |
| `Phone` | Number the caller gave, normalized to 10 digits |
| `Summary` | Two-sentence English summary. Long digit runs are redacted |
| `Sentiment` | `positive`, `neutral`, `negative`, or `distressed` |
| `Outcome` | See below |
| `Language` | Language active at the end of the call, `en` or `hi` |
| `Room ID` | LiveKit room name, which links the row to the session in Agent Insights |

Outcome values, in priority order: `emergency`, `escalated`, `system_error`, `auth_failed`, `customer_not_found`, `claim_status_provided`, `faq_answered`, `no_request`, `abandoned`.

Values are written in raw mode, so a summary beginning with `=` is stored as text and cannot run as a spreadsheet formula.

## Setting up the spreadsheet

1. Create a spreadsheet. Add two tabs named `Customers` and `Interactions`, or set `CUSTOMERS_TAB` and `INTERACTIONS_TAB`.
2. Import [`data/sample/customers.csv`](../data/sample/customers.csv) into `Customers` and [`data/sample/interactions.csv`](../data/sample/interactions.csv) (headers only) into `Interactions`. In `Customers`, format the `Phone` and `PIN` columns as plain text.
3. In [Google Cloud Console](https://console.cloud.google.com), create a project and enable the **Google Sheets API**.
4. Create a **service account**, then add a **JSON key** and download it.
5. Save the key as `agent/service-account.json`. It is git-ignored. Do not commit it.
6. Share the spreadsheet with the service account's `client_email`, with **Editor** access.
7. Set `GOOGLE_SHEET_ID` (the id in the URL, between `/d/` and `/edit`) and `GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json` in `.env`.

Check the connection:

```bash
cd agent
uv run python - <<'PY'
import asyncio
from dotenv import load_dotenv; load_dotenv("../.env")
from integrations import build_store
store = build_store()
print(type(store).__name__)
print(asyncio.run(store.find_customer("5550101001")))
PY
```

It should print `SheetsStore` and the customer record.

## Sample customers

| Phone | Name | PIN | Claim | Status |
| --- | --- | --- | --- | --- |
| 5550101001 | Priya Shah | 1234 | CLM-1001 | Approved, no documents needed |
| 5550101002 | Amit Verma | 4321 | CLM-1002 | Pending documents, with submission steps |
| 5550101003 | Rahul Mehta | 2468 | CLM-1003 | Under review |

These are fictional. The same three records are built into the in-memory fallback store.

## Quotas and scale

Google Sheets allows a limited number of reads per minute per project. Each verification reads the whole Customers tab, which is fine for a demo. For real traffic, move to a database behind the same two methods (`find_customer`, `append_interaction`).

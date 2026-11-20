# Review API

All paths use `/api/v1/`. The API uses Django session authentication; requests
that write data require a valid CSRF cookie and `X-CSRFToken` header.

| Method | Path | Access |
| --- | --- | --- |
| GET | `profiles/{username}/reviews/` | Public; lists reviews received by an active user. |
| GET | `transactions/{uuid}/reviews/` | Participants only; lists reviews for the transaction. |
| POST | `transactions/{uuid}/reviews/` | Participants only; creates a review after the transaction is completed. |

A POST body contains an integer `rating` from 1 to 5 and an optional `comment`
of up to 1,000 characters. The server sets the author and recipient. Each
participant may submit one review per transaction. Successful creation returns
201; invalid input, duplicate reviews, and unfinished transactions return 400.
Unauthenticated requests and nonparticipants are rejected; missing transactions
return 404. Public review responses omit the transaction identifier.

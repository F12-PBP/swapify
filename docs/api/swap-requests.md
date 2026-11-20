# Swap Request API

All paths use `/api/v1/`. The API uses Django session authentication; every
endpoint requires a logged-in user, and requests that write data require a
valid CSRF cookie and `X-CSRFToken` header.

| Method | Path | Access |
| --- | --- | --- |
| GET | `swap-requests/` | Lists swap requests the user sent or received. |
| POST | `swap-requests/` | Sends a new swap request. |
| GET | `swap-requests/{id}/` | Participants only; reads one swap request. |
| POST | `swap-requests/{id}/accept/` | Clothing owner only; accepts a pending request. |
| POST | `swap-requests/{id}/reject/` | Clothing owner only; rejects a pending request. |
| POST | `swap-requests/{id}/cancel/` | Requester only; cancels a pending request. |

The list is paginated by 8 (`count`, `next`, `previous`, `results`) and accepts
optional `page`, `search`, `role` (`sent` or `received`), and `status`
(`pending`, `accepted`, `rejected`, or `cancelled`) query parameters. Invalid
filter values are ignored, matching the web page.

A POST body to `swap-requests/` contains `requested_clothing` and
`offered_clothing` as clothing UUIDs, plus an optional `message` of up to 1,000
characters. The offered piece must belong to the requester, the requested piece
must belong to someone else, both must be available and share an exchange
method, and only one pending request per requested piece is allowed. Successful
creation returns 201; invalid input or a rule violation returns 400.

Each swap request includes the `requester` and `owner` usernames, both clothing
pieces, the viewer's `role`, the `actions` the viewer may take, and the related
`transaction` UUID, `chat_room` ID, and `has_reviewed` flag once the request is
accepted. Actions return 200 with a `detail` message and the updated
`swap_request`. Acting on a request that is no longer pending, or accepting
when a piece is already reserved, returns 409 with a `detail` message. Requests
the user cannot see or act on return 404.

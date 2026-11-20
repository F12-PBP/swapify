# Profile API

All paths use `/api/v1/`. The API uses Django session cookies and CSRF protection.
Call `GET auth/csrf/`, retain cookies, and send the latest `csrftoken` in
`X-CSRFToken` on every POST, PUT, PATCH, or DELETE. Login and registration
rotate the CSRF token; retain updated cookies from their responses. Use HTTPS
outside local development.

| Method | Path | Description |
| --- | --- | --- |
| GET | `auth/csrf/` | Set a CSRF cookie. |
| POST | `auth/register/` | Register with `username`, `name`, `password1`, `password2`, and `community_agreement`; logs the user in. |
| POST | `auth/login/` | Log in using `username` and `password`. |
| POST | `auth/logout/` | End the current session. |
| GET, PATCH | `profile/me/` | Read or update `display_name`, `bio`, and `preferences`. |
| GET | `profiles/{username}/` | Read an active user's public profile. |
| POST | `profile/me/photo/` | Upload `new_profile_picture` as multipart form data. |
| POST | `locations/resolve/` | Resolve `latitude` and `longitude` to area fields and a signed location token. |
| PUT | `profile/me/location/` | Save `district`, `city`, `province`, and optionally `location_token`. |
| POST | `profile/me/onboarding/{step}/` | Save onboarding step 1, 2, or 3. |

Steps accept the same fields as the web forms: step 1 accepts `display_name`,
`bio`, and optional `new_profile_picture`; step 2 accepts location fields,
optional `location_token`, and required `location_agreement`; step 3 accepts
`preferences` and marks onboarding complete. Completing earlier steps is not
tracked as a prerequisite, matching the current web flow. The photo endpoint
accepts JPG, PNG, or WebP up to 5 MB and requires Cloudinary configuration.

Location tokens are bound to the user and expire after 30 minutes. When area
fields are entered manually, changing them clears any previously saved exact
coordinates. Exact coordinates are not included in profile responses.

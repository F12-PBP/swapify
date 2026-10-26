# Marketplace homepage

The Figma Home Page is implemented at `/discover/` (`main:discover`). The public
marketing landing remains at `/`. Discover links in the shared navigation,
footer, and auth layout lead to the marketplace.

## Ownership and review boundaries

| Commit | Responsibility |
| --- | --- |
| `feat(catalog): align discovery categories with style preferences` | Bag/accessory choices, migration, shared preference mapping. |
| `feat(home): add responsive marketplace layout and navigation` | Discover route, shared marketplace header/navigation/footer, safety page. |
| `feat(home): add discovery hero and conditional setup reminder` | Figma photos, hero, incomplete-profile reminder, listing invitation. |
| `feat(catalog): render available discovery cards with real owner data` | Reusable product cards, owner/rating query, pagination, empty state. |
| `feat(catalog): connect discovery filters and preference sorting` | Search, category/size/condition filters, modal drafts, GET state, sorting. |
| `feat(catalog): add private approximate nearby discovery` | Saved-location distance calculation, radius filter, nearest ordering, safe return from location editing. |
| `feat(catalog): implement marketplace item details and related finds` | Detail layout, owner information, related listings, ownership/availability states. |
| `feat(swaps): integrate validated request dialog and add-item return flow` | Progressive enhancement of the existing request endpoint, errors, submission locking, return after listing an offer. |
| Final visual refinement | Responsive captions/cards, matching button icons, filter controls, entry links, CSRF verification. |

Page composition lives in `apps.main`. Marketplace layout includes live under
`apps/main/templates/marketplace/`, and homepage sections under
`main/discovery/`. Catalog queries/cards/details stay in `clothing_catalog`;
swap forms and business rules stay in `swap_request`. No new Django app or
frontend framework is required.

## Behavior

- Discovery shows available items, excluding the signed-in user's own items.
  The existing personal wardrobe remains the destination for managing listings.
- Search uses `search`; other parameters are `type`, `size`, `condition`,
  `distance`, `sort`, and `page`. Filter changes reset pagination and retain
  the other applied criteria. Invalid values are ignored with visible feedback.
- Recommended sorting prioritizes the user's saved style categories and then
  newest listings, with primary key as a stable tie-breaker. Newest is also
  available. Nearest appears only when the viewer has saved coordinates.
- Ratings are real averages of received reviews. Profiles without reviews show
  “New swapper.” Product photos and names are always item data.
- Distances are approximate great-circle distances between saved profile areas,
  calculated and filtered in SQL before pagination. Missing owner locations sort
  last for nearest. The UI shows whole-kilometer approximations and never emits
  coordinates. A manually entered area without saved coordinates cannot enable
  a radius search; the existing location detection/map flow can establish one.
- The distance query uses standard Django math expressions, without PostGIS or
  a new external API. It has been tested on SQLite. A production PostgreSQL
  smoke check and spatial indexing/provider changes are separate deployment
  considerations if catalog scale grows substantially.
- The filter dialog applies drafts only on submission; closing discards them.
  Native dialogs provide focus containment, Escape behavior, and focus return.
  Reduced-motion preferences are respected. Plain GET filters still work
  without JavaScript.
- Product image/title links open details. “Let’s Swap” and “Propose a swap”
  enhance the existing request URL into a dialog. Without JavaScript, the URL
  renders the same form as a full page. Guests sign in and return to that form.
- The dialog offers only the viewer's available pieces. No available offer
  produces an Add Item link with a safe return destination. Submission errors
  preserve the draft, and successful submission opens the request detail page.
- Creation rechecks ownership, availability, and duplicate pending requests
  while locking both items in a transaction. Creation keeps items available;
  the existing acceptance service reserves them.

## Assets and styling

Static Figma assets are local files under `main/images/discovery/`,
`clothing_catalog/images/`, and `swap_request/images/`. The existing Lucide
library supplies matching plus/arrow/close controls. Temporary Figma download
URLs are not referenced at runtime.

Templates use the existing design tokens, fonts, Tailwind utilities, and flexbox.
Small shared component rules live in `theme/static_src/src/marketplace.css`,
imported by the existing stylesheet. Rebuild generated CSS alongside template
or styling changes; do not edit the generated distribution manually.

## Validation and deployment

Run:

```sh
env/bin/python manage.py migrate
env/bin/python manage.py tailwind build
env/bin/python manage.py check
env/bin/python manage.py test --noinput
node --check apps/main/static/main/js/marketplace.js
git diff --check
```

Migration `clothing_catalog.0004_alter_clothing_type` adds Bag and Accessory
choices. Existing items and saved preference values are preserved; legacy Other
items are not automatically recategorized.

Browser checks cover 320, 375, 768, 1024, and 1440 pixel widths, asset loading,
combined filters, discarded modal drafts, mobile request submission, duplicate
errors retaining the message, focus return, and scroll unlocking. Interactive
swap checks use a disposable database outside the repository.

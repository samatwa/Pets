# Phone, keyboard and state checks

## Layout update — November 6, 2026

Cards now use equal-width columns and always show mini charts. The chart/converter
row stretches to the same outer edges as the cards and table, with matching panel
heights. Columns stack at viewport widths up to 640 px. Refresh is in the ten-day
table header beside CSV download. The historical compact-card checks below are
superseded by this layout; browser and physical-device verification remain pending.

All 40 interface, chart and isolated-preview checks passed, including the updated
always-visible mini-chart check. Browser inspection was blocked by an unavailable
browser access host and `Computer Use native pipe is unavailable ... os error 2`.

## Verification status — October 24, 2026

- Compact cards are now 160 px wide with 8 px gaps. Two columns fit when at least 328 px of content width is available, including 360–390 px viewports with 16 px side padding. Cards with mini charts remain 230 px wide.
- A failed first load explicitly reports that no saved values exist. Empty history keeps refresh available and hides inactive filters.
- The 32 interface/preview tests and four localization tests passed. They cover preservation of saved rates after failure, retries, empty history and the preview scenarios below. Preview isolation tests also prohibit real API calls and database writes.
- The new visual and keyboard checks **have not been completed**. Computer Use reported `native pipe is unavailable ... os error 2`; reconnecting and resetting the JavaScript session did not resolve it. Another automation interface returned an empty browser list.
- A physical phone **has not been tested** because no connected phone-control interface is available.

The following items are pending manual checks, not claims of completed verification.

## Language update

The current interface supports English and Norwegian Bokmål. Russian text was replaced with English in errors, terminal reports and internal chart/table fields; the Russian language option was removed. Sessions with the former selection fall back to English. Repeat the pending visual checks in both supported languages.

After this update, all 39 core tests and 33 interface/preview checks passed, including the removed-language session fallback. All 16 Python source/test files were also checked for remaining Cyrillic text; none was found. Physical-device and manual accessibility checks remain pending.

## Isolated state preview

From the project root, run:

```powershell
python -m streamlit run tests_ui/preview_states.py --server.address 127.0.0.1 --server.port 8502
```

The preview uses JSON fixtures from `tests/fixtures`, makes no API calls and does not write to the database. Its sidebar identifies it as **Visual test**. It shows historical fixture data as of October 16, 2026.

| Address | Expected result |
|---|---|
| `http://127.0.0.1:8502/?scenario=normal` | Five rates, chart, converter and table |
| `http://127.0.0.1:8502/?scenario=empty` | Clear invitation to load history and an available refresh button |
| `http://127.0.0.1:8502/?scenario=offline` | API-unavailable warning while saved fixture rates remain visible |
| `http://127.0.0.1:8502/?scenario=first_error` | No history; warning makes no promise to show saved rates; retry remains available |
| `http://127.0.0.1:8502/?scenario=loading` | Loading indicator near refresh for approximately 12 seconds, followed by rates |
| `http://127.0.0.1:8502/?scenario=storage_error` | Clear read-error message without a traceback in the interface |

Open the address afresh when changing scenarios to start a new session. Reload the page to repeat the loading preview. No special scenario parameter has been added to the production application.

## Keyboard walkthrough

1. Open `normal`, enter the document and use Tab / Shift+Tab. If **Skip to main content** appears, activate it with Enter.
2. Check visible focus on the language selector, refresh and card help. Change the language with arrow keys and confirm with the available activation key; labels and numbers should update.
3. Confirm mini charts remain visible after changing language and card selection. Rates, dates and the amount should remain selected.
4. Open rate help without a mouse. Verify that the previous date and period can be read, the tooltip can be closed and navigation can continue.
5. Select a pair and period with arrow keys. Enable comparison with Space. The chart should switch to percentages and single-pair selection should become unavailable. Disabling comparison should restore the previous settings.
6. In the converter, open both selectors, choose currencies with arrow keys and activate the direction swap. Enter `1000.50` and apply with Enter. Decimal-point input is used in every language.
7. Navigate to the table, downloads and expandable sections, then return with Shift+Tab. Check for focus traps and verify that dates stay visible during horizontal table scrolling.
8. Open `empty` and `first_error`. Retry must remain keyboard-accessible; focus must not move to summary controls that are no longer displayed.

## Physical phone

Test Safari on an iPhone or Chrome on Android, recording the actual model, operating system, browser and orientation. Desktop viewport or touch emulation does not replace this check.

For local access, the phone needs the computer's address on the same network, rather than the phone's `localhost`. The preview can be launched with `--server.address 0.0.0.0`, then opened at `http://<computer-IP>:8502/?scenario=normal` on the shared local network. This network-accessible launch has not been performed automatically.

1. In portrait orientation at 360–390 px, check that cards stack into one readable column and that the full EUR/NOK value, signs and percentages are visible.
2. Scroll to the chart and check that the whole page does not shift horizontally and that mini charts remain visible.
3. Tap rate help and inspect a chart value. Confirm that tooltips can be dismissed and do not permanently obscure primary actions.
4. Check wrapping of all five pairs, all four periods, comparison and the legend in both orientations.
5. Swipe the table to UAH/NOK and USD/EUR; each row's date must remain visible. Check vertical page scrolling when the gesture starts over the table.
6. Enter `1000.50` with the on-screen keyboard, apply the value, swap currencies and dismiss the keyboard. Verify that the result remains accessible without clipping.
7. Open `empty`, `loading` and `first_error`. Check messages, retry behavior and the absence of unexpected page jumps after loading.

| Device / OS / browser | Touch and tooltips | Table | Summary | Errors | Result |
|---|---|---|---|---|---|
| Not tested | — | — | — | — | Awaiting a physical device |

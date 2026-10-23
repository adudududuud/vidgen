# Changelog

## 1.1.0

- Fix blurry fonts on high-DPI Windows by opting in to per-monitor v2 DPI awareness prior to Tk initialization.
- Make the entire content vertically scrollable so footer/status stay reachable on short screens.
- Make action buttons symmetrical: 4 columns on wide windows, 2 columns on narrower windows.
- Improve combobox contrast and normalize input/button sizing.
- Prefer a smart compatible format and retry once with raw available formats **only** for unavailable-format errors.
- Add friendly diagnostic messages for platform restrictions and network failures without bypassing access controls.
- Add layout smoke test and additional regression tests (34 total on Linux). Actual Windows installation and full-video playback require separate verification.

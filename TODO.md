# YouTube Screenshot Grabber - TODO List

## Bug Fixes
- [ ] Fix map tiles not loading in location dialog
  - Investigate map display/loading issues
  - Ensure proper initialization and cleanup of map widget
  - Consider alternative map tile providers if needed

## Feature Enhancements

### Multiple YouTube URLs Support
- [ ] Convert YouTube URL input to support multiple URLs
  - Make input field multiline
  - Parse input text into separate lines
  - Validate each line as YouTube video URL
  - Store valid URLs in config file as array
  - Update screenshot logic to capture from all videos at interval

### Theme Improvements
- [ ] Implement consistent dark theme
  - Apply dark theme to all windows and dialogs
  - Add dark theme support for context menu
  - Ensure proper contrast and readability

### Output Format Options
- [ ] Add configurable screenshot format
  - Add setting for PNG/JPG output format
  - Update ffmpeg command to support both formats
  - Add format selection to settings menu
  - Save format preference in config file

## Technical Debt
- [ ] Refactor screenshot capture logic to handle multiple URLs
- [ ] Improve error handling for invalid YouTube URLs
- [ ] Add proper validation for video format compatibility

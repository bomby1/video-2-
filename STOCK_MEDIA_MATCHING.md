# Stock Media Matching Feature

## Overview
Added automatic stock media matching functionality to the CapCut automation pipeline. This feature runs after video generation completes and before exporting the video.

## What It Does
The automation now performs these steps after video generation:

1. **Click "Scenes"** - Finds and clicks the "Scenes" button in the left sidebar
2. **Click "Media" tab** - Switches to the Media tab (from Voiceover)
3. **Click "Match stock media"** - Initiates the stock media matching process
4. **Confirm popup** - Clicks "Continue" on the confirmation dialog
5. **Wait 90 seconds** - Allows CapCut to complete the stock media matching

## Workflow Integration

### Before:
```
Video Generation → Export → Download
```

### After:
```
Video Generation → Match Stock Media → Export → Download
```

## Implementation Details

### New Method: `match_stock_media()`
- Location: `src/main.py` (lines 695-857)
- Returns: `True` if successful, `False` if any step fails
- Timeout: 90 seconds for matching completion

### Integration Point
- Called in: `process_single_job()` method
- Step: 6.5 (between generation and export)
- Behavior: If matching fails, shows warning but continues with export

## Selectors Used

### Scenes Button
- `button:has-text('Scenes')`
- `div:has-text('Scenes')`
- `[aria-label*='Scenes' i]`

### Media Tab
- `button:has-text('Media')`
- `[role='tab']:has-text('Media')`

### Match Button
- `button:has-text('Match')`
- `button:has-text('Match stock media')`

### Continue Button
- `button:has-text('Continue')`
- `[role='dialog'] button:has-text('Continue')`

## Error Handling
- If any step fails, the automation logs a warning and continues
- Does not stop the entire pipeline if stock media matching fails
- Provides detailed console output for debugging

## Console Output Example
```
============================================================
🎬 Matching Stock Media
============================================================
1️⃣ Looking for 'Scenes' button in left sidebar...
   ✅ Found 'Scenes' button with: button:has-text('Scenes')
   ✅ Clicked 'Scenes' button
2️⃣ Looking for 'Media' tab...
   ✅ Found 'Media' tab with: button:has-text('Media')
   ✅ Clicked 'Media' tab
3️⃣ Looking for 'Match stock media' button...
   ✅ Found 'Match stock media' button: 'Match'
   ✅ Clicked 'Match stock media' button
4️⃣ Looking for 'Continue' button in confirmation popup...
   ✅ Found 'Continue' button with: button:has-text('Continue')
   ✅ Clicked 'Continue' button
5️⃣ Waiting 90 seconds for stock media matching to complete...
   ⏱️  90 seconds remaining...
   ⏱️  80 seconds remaining...
   ...
✅ Stock media matching completed!
```

## Testing
To test the feature:
1. Run the automation normally: `py -u main.py` (from src folder)
2. Or use the batch file: `run_realtime.bat`
3. Watch for the "Matching Stock Media" section in console output
4. Verify that stock media is matched before export begins

## Notes
- The 90-second wait time can be adjusted in the code if needed
- Real-time console output is enabled with `-u` flag or `run_realtime.bat`
- Feature is automatically enabled for all video processing jobs

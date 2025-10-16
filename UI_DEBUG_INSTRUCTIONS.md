# UI Debugging Instructions

## Current Status

The web UI has been enhanced with comprehensive debug logging to help diagnose the "not clickable" issue. The HTML, JavaScript, and onclick handlers are all correctly in place.

## How to Debug

### Step 1: Start the Server

```bash
./start.sh
```

Or manually:
```bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate scholarbot
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

### Step 2: Open Browser Developer Tools

1. Open your browser (Firefox, Chrome, Edge, etc.)
2. Navigate to: http://localhost:8000/authors
3. Open Developer Tools:
   - **Firefox/Chrome/Edge**: Press `F12` or `Ctrl+Shift+I` (Linux/Windows) / `Cmd+Option+I` (Mac)
   - Or right-click anywhere and select "Inspect" or "Inspect Element"

### Step 3: Check the Console Tab

In the Developer Tools window, click on the "Console" tab. You should see debug messages like:

```
===== Scholar Bot UI Loading =====
Location: http://localhost:8000/authors
User Agent: Mozilla/5.0 ...
===== JavaScript Functions Loading =====
toggleSidebar function defined
toggleDarkMode function defined
showToast function defined
Setting up HTMX event listeners
===== All JavaScript Functions Loaded =====
Available functions: {toggleSidebar: 'function', toggleDarkMode: 'function', showToast: 'function'}
DOM Content Loaded
HTMX available: true
Tailwind loaded: true
===== Authors Page JavaScript Loading =====
showAddAuthorModal function defined
===== Authors Page JavaScript Loaded =====
Available functions: {showAddAuthorModal: 'function', hideAddAuthorModal: 'function', ...}
```

### Step 4: Test Click Interactivity

Try clicking the "Add Author" button. Watch the Console for messages like:

```
showAddAuthorModal called
Modal element: [object HTMLDivElement]
Modal should now be visible
```

If you see these messages, JavaScript IS working.

### Step 5: Common Issues & Solutions

#### Issue A: No Console Messages at All

**Diagnosis**: JavaScript is disabled or blocked
**Solutions**:
1. Check browser settings for JavaScript (should be enabled)
2. Check if you have browser extensions blocking JavaScript (NoScript, uBlock Origin, etc.)
3. Try a different browser or incognito/private mode

#### Issue B: Console Shows Errors Like "Failed to load..."

**Diagnosis**: CDN scripts are blocked
**Solutions**:
1. Check if you're behind a firewall or proxy blocking cdn.tailwindcss.com, unpkg.com, cdn.jsdelivr.net
2. Check browser Network tab (F12 → Network tab) and look for failed requests (red)
3. Try disabling content blockers or ad blockers temporarily

#### Issue C: Console Messages Appear But Nothing Happens When Clicking

**Diagnosis**: Possible CSS issue (elements may be covered by another layer)
**Solutions**:
1. Check if elements have correct z-index
2. Check if pointer-events are disabled
3. Try clicking exactly on the text inside buttons

#### Issue D: "Cannot read property of null"

**Diagnosis**: Elements not found in DOM
**Solution**: Refresh the page, the templates may not have loaded correctly

### Step 6: Test with Simple HTML

If the main UI still doesn't work, test with the minimal test file:

```bash
# Open in browser:
file:///home/eik-tb/OneDrive_andreaivan.costantino@kuleuven.be/GitHub/scholar-slack-bot/test_ui.html
```

If this test file works but the main UI doesn't, the issue is specific to the HTMX/Tailwind integration.

## Alternative: Use Traditional Forms (Like Old GUI)

If the JavaScript approach continues to fail, we can convert critical actions to traditional HTML forms with POST methods (like the old gui.py):

**Example conversion**:
```html
<!-- Current (JavaScript) -->
<button onclick="showAddAuthorModal()">Add Author</button>

<!-- Traditional Form Approach -->
<form method="post" action="/web/add-author">
    <input type="text" name="scholar_id" required>
    <button type="submit">Add Author</button>
</form>
```

This requires NO JavaScript and works exactly like the old gui.py did.

## What We've Confirmed Working

✅ HTML structure is valid
✅ JavaScript functions are defined
✅ onclick handlers are present in HTML
✅ HTMX library loads successfully
✅ Tailwind CSS loads successfully
✅ Server responds correctly (200 OK)
✅ API endpoints work (/api/v1/authors, etc.)

## Next Steps

1. **Try opening http://localhost:8000/authors in your browser**
2. **Open Developer Tools (F12) and look at the Console tab**
3. **Report back what you see in the console**
4. **Try clicking the "Add Author" button and report if console shows messages**

Based on what you see, we'll know exactly what the issue is:

- If console shows function calls → JavaScript works, might be CSS issue
- If console shows nothing → JavaScript is blocked/disabled
- If console shows errors → Specific error to fix

---

## Browser Compatibility

The UI should work on:
- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+

Older browsers may not support all features.

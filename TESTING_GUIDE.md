# Testing Guide - End-to-End RFI Agent Workflow

**Quick Test**: 2-5 minutes to verify all fixes are working

---

## Pre-Test Checklist

- ✅ Backend running on `http://localhost:8000`
- ✅ Frontend running on `http://localhost:5173`
- ✅ `.env` file has `SUPABASE_SERVICE_ROLE_KEY` added
- ✅ `config.py` validates the key on startup
- ✅ All Python files compile without errors

---

## Test 1: Document Upload (Fix: AsyncIO + Chunker)

### Steps
1. Open RFI Agent page in frontend
2. Click "Upload Documents" or drag a PDF
3. Select any PDF file (test files in `backend/sample_data/`)

### Expected Results
- Upload begins immediately
- Progress spinner shows for **3-10 seconds** (not infinite)
- Success message: `✓ X chunks indexed from 1 files`
- Document appears in library on left panel
- No hanging or timeout errors

### What to Check in Logs
```
[STEP 1] PDF extraction complete: success=True
[STEP 2] Extracted 17 pages
[STEP 3] Table extraction starting...
[STEP 4] Table extraction complete: 25 tables found
[STEP 5] Base metadata created
[STEP 6] Chunking starting...
[STEP 7] Embedding generation started
[STEP 8] Embedding generation complete
[STEP 9] Chroma insertion started
[STEP 10] Chroma insertion complete
[STEP 11] Returning response
```

✅ **PASS**: All steps logged sequentially, no hangs

---

## Test 2: RFI Query (Fix: Supabase RLS)

### Steps
1. After uploading a document
2. In chat box, type a question: `"What is the ambient temperature requirement?"`
3. Click "Ask"

### Expected Results
- Chat shows user question
- Loading spinner appears
- Response text from Cerebras LLM appears
- **Citations section displays below response** with:
  - `[SOURCE 1]` with filename
  - `Type:` showing document type
  - `Relevance:` showing percentage (e.g., 95%)

### What to Check in Logs
```
Processing RFI question: What is the ambient temperature requirement?...
Retrieved 6 documents from ChromaDB
RFI answered in 2345ms with confidence: HIGH
RFI logged successfully  ← ✅ NO 401 ERROR
```

✅ **PASS**: No "401 Unauthorized" errors, log_rfi() succeeds

### Database Verification (Optional)
1. Go to Supabase dashboard
2. Navigate to `rfi_log` table
3. Should see new row with:
   - question: "What is the ambient temperature requirement?"
   - answer: (full response text)
   - citations_json: (JSON array of sources)
   - created_at: (current timestamp)

✅ **PASS**: Row exists without 401 error

---

## Test 3: Markdown Rendering (Fix: Frontend)

### Steps
1. Ask question that will return markdown in response (any question works, LLM often uses bold)
2. Look at the response text

### Expected Results
**ANY of these should render properly**:

- **Bold text**: `**Project Specification**` → appears as **Project Specification** (bold, not with asterisks)
- *Italic text*: `*temperature requirements*` → appears as *temperature requirements* (italic, not with asterisks)
- `Code snippets`: `` `Section 3.2.1` `` → appears with gray background, monospace font
- [Links]: `[AWS Docs](https://aws.amazon.com)` → appears as blue underlined link, opens in new tab

### What to Check Visually
- ❌ **FAIL**: Response shows `**bold**` (double asterisks visible)
- ✅ **PASS**: Response shows text in bold formatting (no asterisks)

### Browser Console Check
- No errors in browser console (F12 → Console tab)
- React should not complain about invalid children

✅ **PASS**: Markdown renders correctly, no console errors

---

## Test 4: Full Workflow

### Complete End-to-End Test

**Step 1: Upload**
```
Frontend → Select PDF → Upload completes in <10s
✅ PASS: No hanging
```

**Step 2: Ingest**
```
Backend → Extract → Chunk → Embed → Store in ChromaDB
✅ PASS: All steps logged
```

**Step 3: Query**
```
Frontend → Ask question → Sent to backend
Backend → Retrieve docs → Call Cerebras LLM → Log to Supabase
✅ PASS: No 401 error during logging
```

**Step 4: Display**
```
Frontend → Receive response
  1. Parse markdown
  2. Render **bold**, *italic*, `code`
  3. Display citations
✅ PASS: Proper formatting
```

---

## Common Issues & Fixes

### Issue 1: "401 Unauthorized: new row violates RLS policy"
**Cause**: Service role key not set or not loaded  
**Fix**:
1. Verify `.env` has `SUPABASE_SERVICE_ROLE_KEY`
2. Check `config.py` loads it (startup message should say "SUPABASE_SERVICE_ROLE_KEY environment variable is required")
3. Restart backend

### Issue 2: Upload still hangs
**Cause**: Async/chunker fixes not deployed  
**Fix**:
1. Verify `rfi_agent.py` has `ingest_project_document_async()`
2. Check endpoint uses `await ingest_multiple_documents_async()`
3. Verify `chunker.py` has backward movement detection

### Issue 3: Markdown shows `**text**` instead of **text**
**Cause**: MarkdownRenderer not imported or used  
**Fix**:
1. Verify `MarkdownRenderer.jsx` exists in `components/`
2. Check `RFIAgent.jsx` imports it
3. Check rendering uses `<MarkdownRenderer text={msg.text} />`

### Issue 4: Response shows in loading state forever
**Cause**: Frontend timeout or response never received  
**Fix**:
1. Check backend is running (`http://localhost:8000/health`)
2. Check network tab (F12 → Network) for request status
3. Look for backend errors in console

---

## Automated Test (Optional)

Create `test_e2e.py` in backend:
```python
import requests
import json

BASE_URL = "http://localhost:8000"

# Test 1: Health check
print("Test 1: Health check")
resp = requests.get(f"{BASE_URL}/health")
assert resp.status_code == 200
print("✅ PASS: Backend running")

# Test 2: Query without documents (should work but with confidence LOW)
print("\nTest 2: Query RFI")
resp = requests.post(f"{BASE_URL}/api/rfi/query", 
  json={"question": "What is the temperature requirement?"})
assert resp.status_code == 200
data = resp.json()
assert "answer" in data
assert "citations" in data
assert data["answer_confidence"] in ["HIGH", "MEDIUM", "LOW"]
print(f"✅ PASS: Got response with {len(data['citations'])} citations")

# Test 3: Check Supabase logging worked
print("\nTest 3: Get RFI history")
resp = requests.get(f"{BASE_URL}/api/rfi/history?limit=1")
assert resp.status_code == 200
history = resp.json()
if history.get("rfis"):
    print(f"✅ PASS: Found {len(history['rfis'])} RFI in history")
else:
    print("⚠️  WARNING: No history yet (normal on first run)")

print("\n🎉 All tests passed!")
```

Run with:
```bash
python test_e2e.py
```

---

## Success Criteria

✅ **All of these must pass**:
1. Upload completes in < 10 seconds
2. No "401 Unauthorized" errors in logs
3. `rfi_log` table receives entries in Supabase
4. Markdown text displays formatted (not raw symbols)
5. Citations render below response
6. No JavaScript errors in browser console

---

## Rollback (If Issues Found)

If tests fail, revert to last known good state:
```bash
git status                    # See what changed
git log --oneline -5          # See recent commits
git diff HEAD~1 HEAD          # See recent changes
git reset --hard HEAD~1       # Rollback if needed
```

---

## Next Steps After Testing

✅ If all tests pass:
- Deploy to staging environment
- Run load tests with multiple concurrent uploads
- Test with various PDF formats and sizes
- Verify performance metrics

⚠️ If issues found:
- Check specific error message from testing
- Review corresponding fix in this guide
- Ensure all files are updated
- Restart services

---

## Support

For debugging:
- Check backend logs: Look for `ERROR` or `Exception` messages
- Check frontend logs: Browser console (F12 → Console tab)
- Check database: Supabase dashboard → `rfi_log` table
- Verify network: Browser network tab (F12 → Network tab)


# Code Review & Refactoring Notes

## Current State
- **Total Lines**: ~2,248 lines
- **Backend**: app.py (227 lines) ✅ Clean
- **Frontend**: index.html (1,264 lines) ⚠️ Needs extraction
- **Modules**: 4 JS files (662 lines) ✅ Mostly clean

## Issues Found

### 🔴 Critical
1. **Massive inline JavaScript in HTML** (800+ lines)
   - Should be extracted to separate module
   - Hard to maintain and test
   - Violates separation of concerns

2. **No input validation on backend**
   - Missing length checks on descriptions
   - No validation on intervals data structure
   - SQL injection risk (mitigated by parameterized queries)

3. **Error handling incomplete**
   - Generic catch-all exceptions
   - No logging
   - No retry logic for OpenAI API

### 🟡 Medium
4. **Duplicate timer logic**
   - Main timer and focus timer have separate state
   - Could be unified into single timer class

5. **No caching**
   - OpenAI responses not cached
   - Database queries not optimized

6. **Missing CSP headers**
   - Security headers could be stronger

### 🟢 Low
7. **Code organization**
   - Could use blueprints for routes
   - Could separate config from code

8. **Missing tests**
   - No unit tests
   - No integration tests

## Refactoring Plan

### Phase 1: Extract Inline JS ✅
- Create `static/main.js` for main timer logic
- Create `static/ui-controller.js` for UI updates
- Keep HTML minimal

### Phase 2: Add Validation ✅
- Backend input validation middleware
- Frontend validation before API calls

### Phase 3: Error Handling ✅
- Structured error responses
- Add logging
- Retry logic for API calls

### Phase 4: Performance ✅
- Add response caching
- Optimize database queries
- Lazy load modules

### Phase 5: Security ✅
- Strengthen CSP headers
- Add rate limiting
- Input sanitization


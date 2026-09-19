# Auto-Claim Threshold Parameter Fix

## TL;DR

> **Quick Summary**: Fix the `auto_claim_query` function's threshold parameter handling - correct tuple syntax bug, complete docstring, and update agent.py FunctionTool and dispatch handler to pass the dynamic threshold from user questions.
> 
> **Deliverables**: 
> - Fixed `functions_auto_claim.py` with proper tuple parameter binding and complete docstring
> - Updated `agent.py` with threshold parameter in FunctionTool and dispatch handler
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: NO - sequential
> **Critical Path**: Fix function → Update agent tool → Update dispatch → Verify

---

## Context

### Current State
- `functions_auto_claim.py` line 115: `def auto_claim_query(threshold: float = 10000.0) -> dict:` - parameter added
- Line 129: `cursor.execute(_AUTO_CLAIM_QUERY, (threshold))` - **BUG**: missing trailing comma, not a tuple
- Lines 116-124: Docstring incomplete (`"""float` at start, no param documentation)
- `agent.py` lines 88-97: `auto_claim_tool` has empty properties - needs `threshold` parameter
- `agent.py` line 260: `auto_claim_query()` called without arguments - needs to pass threshold

### Required Changes
1. Fix tuple syntax: `(threshold,)` not `(threshold)`
2. Complete docstring with proper parameter documentation
3. Add `threshold` parameter to `auto_claim_tool` FunctionTool in agent.py
4. Update dispatch handler to pass `**json.loads(item.arguments)`
5. Update TOOL SELECTION GUIDE in instructions

---

## Verification Strategy

- **Test**: py_compile both files
- **Test**: Run `auto_claim_query(15000.0)` returns only Mary Johnson (24000)
- **Test**: Run `auto_claim_query()` (default) returns both customers
- **Test**: Verify agent.py compiles and FunctionTool schema includes threshold

---

## TODOs

- [ ] 1. Fix functions_auto_claim.py tuple syntax and docstring

  **What to do**:
  - Change line 129: `cursor.execute(_AUTO_CLAIM_QUERY, (threshold))` → `cursor.execute(_AUTO_CLAIM_QUERY, (threshold,))`
  - Fix docstring (lines 116-124): proper opening `"""`, document `threshold` parameter with type and default

  **QA Scenarios**:
  - `auto_claim_query(15000.0)` returns 1 customer (Mary Johnson, 24000)
  - `auto_claim_query()` returns 2 customers (default 10000)
  - `auto_claim_query(20000.0)` returns 0 or 1 customer
  - Verify no TypeError on execute

  **Commit**: YES - `fix: correct threshold tuple binding and docstring`

- [ ] 2. Update agent.py FunctionTool and dispatch handler

  **What to do**:
  - Lines 88-97: Add `threshold` property to `auto_claim_tool` parameters:
    ```python
    "threshold": {
        "type": "number",
        "description": "the claim amount threshold to filter customers (e.g. 15000). Defaults to 10000 if not specified.",
    }
    ```
    Add to required? No - make optional with default handled by function
  - Line 260: Change `auto_claim_query()` → `auto_claim_query(**json.loads(item.arguments))`
  - Line 199: Update TOOL SELECTION GUIDE: mention threshold parameter extraction from question

  **QA Scenarios**:
  - py_compile agent.py passes
  - FunctionTool schema includes threshold as optional number
  - Dispatch handler correctly passes threshold from model arguments

  **Commit**: YES - `feat: add threshold parameter to auto_claim_query tool`

---

## Final Verification Wave

- [ ] F1. **Syntax Check** — `python -m py_compile functions_auto_claim.py agent.py` → both PASS
- [ ] F2. **Function Test** — `python -c "from functions_auto_claim import auto_claim_query; import json; print(json.dumps(auto_claim_query(15000.0), indent=2))"` → returns 1 customer
- [ ] F3. **Default Test** — `python -c "from functions_auto_claim import auto_claim_query; import json; print(json.dumps(auto_claim_query(), indent=2))"` → returns 2 customers

---

## Commit Strategy

- 1: `fix: correct threshold tuple binding and docstring` - functions_auto_claim.py
- 2: `feat: add threshold parameter to auto_claim_query tool` - agent.py

---

## Success Criteria

### Verification Commands
```bash
python -m py_compile functions_auto_claim.py agent.py  # Expected: no errors
python -c "from functions_auto_claim import auto_claim_query; import json; print(json.dumps(auto_claim_query(15000.0), indent=2))"  # Expected: 1 customer (Mary)
python -c "from functions_auto_claim import auto_claim_query; import json; print(json.dumps(auto_claim_query(), indent=2))"  # Expected: 2 customers
```

### Final Checklist
- [ ] Tuple syntax fixed: `(threshold,)` with trailing comma
- [ ] Docstring complete and documents threshold parameter
- [ ] agent.py FunctionTool includes threshold property
- [ ] Dispatch handler passes arguments correctly
- [ ] All py_compile pass
- [ ] Live tests return expected results
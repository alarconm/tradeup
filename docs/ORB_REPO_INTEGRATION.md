# ORB_repo Integration Guide

This document describes the changes needed in the ORB_repo listing app to support TradeUp member tagging.

## Overview

When listing trade-in items from a TradeUp member, staff need to tag products with the member's number (e.g., `TU1001`) so the TradeUp system can track sales and calculate cashback rewards.

## Changes Required

### 1. Add `normalize_member_tag` function to `app.py`

Add this function after `normalize_orb_tag()` (around line 557):

```python
def normalize_member_tag(raw_value: str | None) -> str | None:
    """Normalize user-supplied TradeUp member tag to canonical TU#### format.

    Used for TradeUp Membership program trade-ins. When items are listed with
    this tag, the system can track sales and issue cashback rewards based on
    the member's tier.
    """
    if raw_value is None:
        return None

    candidate = raw_value.strip().upper().replace(' ', '')
    if not candidate:
        return None

    # Remove optional TU prefix before sanitizing
    if candidate.startswith('TU'):
        candidate = candidate[2:]

    # Keep only alphanumeric characters
    candidate = re.sub(r'[^A-Z0-9]', '', candidate)
    if not candidate:
        return None

    return f"TU{candidate}"
```

### 2. Update `/api/process-shopify-direct` route (around line 6247)

Add member tag handling after consignment tag handling:

```python
# After consignment_tag handling (around line 6252):
member_enabled = request.form.get('member_enabled', 'false').lower() == 'true'
member_tag = None
if member_enabled:
    member_tag = normalize_member_tag(request.form.get('member_tag'))
    if not member_tag:
        return jsonify({'success': False, 'error': 'TradeUp Member# is required when the toggle is enabled'}), 400

# Combine tags
extra_tags = []
if consignment_tag:
    extra_tags.append(consignment_tag)
if member_tag:
    extra_tags.append(member_tag)
```

### 3. Update `create_shopify_products_direct` call

Pass the combined extra_tags to the function:

```python
results = create_shopify_products_direct(
    input_path,
    shopify_config,
    case_override,
    generate_labels,
    extra_tags=extra_tags if extra_tags else None,
)
```

### 4. Add UI Toggle to `templates/web/card_intake.html`

Add this after the consignment toggle (around line 724):

```html
<div class="member-toggle">
    <label class="toggle-label">
        <input type="checkbox" id="memberToggle" onchange="toggleMemberInput()">
        <span>TradeUp Member</span>
    </label>
    <div id="memberInputGroup" class="input-with-prefix" style="display: none;">
        <span class="input-prefix">TU</span>
        <input type="text" id="memberTag" class="input-field input-field--sm" placeholder="1001" style="width: 70px;">
    </div>
</div>
```

### 5. Add JavaScript for member toggle

Add this function after `toggleConsignmentInput()`:

```javascript
function toggleMemberInput() {
    var checkbox = document.getElementById('memberToggle');
    var inputGroup = document.getElementById('memberInputGroup');
    var input = document.getElementById('memberTag');
    if (checkbox.checked) {
        inputGroup.style.display = 'flex';
        input.focus();
    } else {
        inputGroup.style.display = 'none';
        input.value = '';
    }
}
```

### 6. Update `pushToShopify()` function

In the `pushToShopify()` function, add member tag to FormData:

```javascript
// After consignment handling:
var memberToggle = document.getElementById('memberToggle');
var memberEnabled = memberToggle && memberToggle.checked;
if (memberEnabled) {
    var memberTag = document.getElementById('memberTag').value.trim();
    if (!memberTag) {
        alert('Please enter a TradeUp Member# or disable the toggle');
        return;
    }
    formData.append('member_enabled', 'true');
    formData.append('member_tag', memberTag);
}
```

## Usage

1. When processing a trade-in from a TradeUp member:
   - Enable the "TradeUp Member" toggle
   - Enter the member's number (just the digits, e.g., "1001")
   - Push to Shopify as normal

2. The product will be tagged with `TU1001` (or whatever member number)

3. When the item sells, the TradeUp platform webhook will:
   - Match the product to the member by tag
   - Calculate cashback based on the member's tier
   - Issue store credit to the member

## Notes

- The member tag is SEPARATE from the consignment tag (#ORB)
- Both can be used simultaneously (though unusual)
- Member tags follow format: `TU{number}` (e.g., `TU1001`, `TU1002`)
- Consignment tags follow format: `#ORB{number}` (e.g., `#ORB123`)

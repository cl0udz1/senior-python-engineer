# Discount fix

Changed the dictionary lookup in `discount_percent` to `.get(membership, 0)`.
This preserves the `basic` and `premium` discounts while returning zero for
`None` and unrecognized strings instead of raising `KeyError`. Both public
function signatures and `every_other_helper` are unchanged.

## Verification performed

Ran a standard-library assertion script using `python -B -` from this project:

- Checked `None → 0`, `basic → 5`, `premium → 10`, and `unknown → 0`.
- Checked the unrecognized strings `''`, `'Premium'`, and `' basic '` return zero.
- Checked both function signatures, the helper's behavior for `' Basic '`, and
  that the helper's source exactly matches its original text.

Result: all assertions passed; exit status 0. No dependencies, formatting tools,
or project configuration were changed.

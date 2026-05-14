"""Manual demo script for validating single-fund quote lookup."""

from __future__ import annotations

import json
import sys

from fund_quote import get_fund_quote


def main() -> None:
    fund_code = sys.argv[1] if len(sys.argv) > 1 else "023350"
    fund_name = sys.argv[2] if len(sys.argv) > 2 else ""
    result = get_fund_quote(fund_code=fund_code, fund_name=fund_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

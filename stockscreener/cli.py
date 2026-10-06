from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    p = argparse.ArgumentParser(prog="stockscreener", description="S&P 500 opportunity screener")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="fetch data, score every S&P 500 stock, write the HTML report")
    r.add_argument("--refresh", action="store_true", help="ignore the 6h cache and re-download everything")
    r.add_argument("--open", action="store_true", help="open the report in your browser when done")

    b = sub.add_parser("backtest", help="replay the scoring model on past data and measure whether high scores moved")
    b.add_argument("--years", type=float, default=5.0)
    b.add_argument("--refresh", action="store_true")

    args = p.parse_args()

    if args.cmd == "run":
        from . import pipeline, report
        df = pipeline.run(refresh=args.refresh)
        html, csv = report.write_outputs(df)
        print(f"\nReport: {html}\nCSV:    {csv}")
        if args.open and sys.platform == "darwin":
            subprocess.run(["open", html])
    elif args.cmd == "backtest":
        from . import backtest
        backtest.run(years=args.years, refresh=args.refresh)


if __name__ == "__main__":
    main()

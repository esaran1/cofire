#!/usr/bin/env bash
# Lighthouse, mobile, against the static build served locally (scripts/serve_static.py),
# three runs per page, median performance reported. Usage: scripts/lighthouse_static.sh LABEL
# Needs Lighthouse (LIGHTHOUSE=path/to/lighthouse/cli/index.js, or `npx lighthouse`) and Chrome.
set -euo pipefail
LABEL=${1:?label}
OUT=artifacts/v13/lighthouse/$LABEL
mkdir -p "$OUT"
BASE=${STATIC_URL:-http://127.0.0.1:4100/cofire/}
CELL=$(python3 -c "import json;i=json.load(open('app/out/data/domains/index.json'));b=json.load(open(f'app/out/data/domains/denver/{i[\"issues\"][-1]}.json'));print(b['cells'][0]['id'])")
LH=${LIGHTHOUSE:-}
run() { if [ -n "$LH" ]; then node "$LH" "$@"; else npx --yes lighthouse "$@"; fi; }
for page in map card brief; do
  case $page in
    map) url="${BASE}?domain=denver" ;;
    card) url="${BASE}?domain=denver&cell=${CELL}" ;;
    brief) url="${BASE}brief/" ;;
  esac
  for i in 1 2 3; do
    run "$url" --quiet --only-categories=performance,accessibility,best-practices --form-factor=mobile \
      --chrome-flags="--headless=new" --output=json --output-path="$OUT/${page}_${i}.json" >/dev/null 2>&1
  done
done
python3 - "$OUT" <<'PY'
import json, statistics, sys, glob, os
out = sys.argv[1]; res = {}
for page in ("map", "card", "brief"):
    runs = [json.load(open(f)) for f in sorted(glob.glob(f"{out}/{page}_*.json"))]
    perf = [round(r["categories"]["performance"]["score"] * 100) for r in runs]
    a11y = [round(r["categories"]["accessibility"]["score"] * 100) for r in runs]
    bp = [round(r["categories"]["best-practices"]["score"] * 100) for r in runs]
    med = sorted(runs, key=lambda r: r["categories"]["performance"]["score"])[len(runs) // 2]
    au = med["audits"]
    res[page] = {"performance_runs": perf, "performance_median": statistics.median(perf), "accessibility_median": statistics.median(a11y),
                 "best_practices_median": statistics.median(bp),
                 "lcp_ms": round(au["largest-contentful-paint"]["numericValue"]), "tbt_ms": round(au["total-blocking-time"]["numericValue"]),
                 "fcp_ms": round(au["first-contentful-paint"]["numericValue"]), "cls": round(au["cumulative-layout-shift"]["numericValue"], 3),
                 "si_ms": round(au["speed-index"]["numericValue"])}
    for f in glob.glob(f"{out}/{page}_*.json"): os.remove(f)
json.dump(res, open(f"{out}/summary.json", "w"), indent=1)
print(json.dumps(res, indent=1))
PY

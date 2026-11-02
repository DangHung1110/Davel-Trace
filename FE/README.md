# Frontend

Static pages that drive the backend, no build step. Run `python server.py` from the repo
root, then open `http://127.0.0.1:5500/FE/<page>`.

- `test_harness.html`: text to plans, then review, repair and "Chot plan".
- `onboard.html`: the onboarding profile (three archetypes or custom), kept in localStorage.

The review pages are generated and not committed:

```bash
python BE/tools/build_plan_review.py --reuse        # plan_review.html: 24 plans, blind human review
python BE/tools/build_verify_page.py --mode review  # verify_review.html
python BE/tools/build_verify_page.py --mode sample  # verify_sample.html
python BE/tools/build_review_report.py              # verify_result.html
```

The Flutter app lives on `feat/product-platform`.

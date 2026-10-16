# Remotion license determination

**Determination: this project may use Remotion under its free license.**

- **What is used:** Remotion 4.0.531 and its official packages
  (`remotion`, `@remotion/cli`, which brings in `@remotion/bundler`,
  `@remotion/renderer` and the others it depends on). Versions are pinned
  in `film/package.json` and locked in `film/package-lock.json`.
- **Who uses it:** an individual student, making a demo video
  for a student competition entry. No company is involved, and nothing is
  sold.
- **What the license says:** Remotion's license is at
  <https://remotion.dev/license>, which redirects to
  <https://github.com/remotion-dev/remotion/blob/main/LICENSE.md>. As read
  on 2026-10-15, it grants the free license to, among others:
  - "an individual";
  - "a for-profit organization with up to 3 employees";
  - "a non-profit or not-for-profit organization";
  - anyone "evaluating whether Remotion is a good fit".

  A company license is required only for for-profit organizations above
  that size. The license does not mention students. An individual student
  falls under "an individual".
- **Conditions we follow:**
  - The free license covers making videos and images, and modifying the
    software.
  - It does not allow copying or modifying Remotion's code "for the purpose
    of selling, renting, licensing" it. We do neither.
  - The license notes it will change in Remotion 5.0. This project pins 4.x.
    Re-read the license before upgrading to 5.
- **Rendering is local only:**
  - No Remotion Lambda, Cloud Run or other hosted rendering is used.
  - No account was created.
  - The browser is the Chrome for Testing headless shell that Playwright had
    already installed. Remotion downloaded nothing at render time.

If the project is ever taken over by an organization (for example, a school
club that charges fees, or a company), re-check eligibility before
rendering again.

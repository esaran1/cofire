# Third-party assets, data and code

Everything COFIRE shows or is built from that it did not create, with the
terms it is used under and where the credit appears. The app's Method page
renders the data, map and photo credits from `app/lib/facts.json`
(`cofire/ship/facts.py`, `_credits`).

## Shown in the app

| Asset | Used for | Terms | Credit shown |
|---|---|---|---|
| High Park fire near Poudre Canyon, Colorado (2012), photo by DVIDSHUB, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:High_Park_fire_near_Poudre_Canyon,_Colorado.jpg) | landing page | CC BY 2.0, attribution required | landing page, beneath the photo: author, license link, source link; Method page |
| OpenStreetMap tiles | map basemap | ODbL (data), tiles CC BY-SA; tile usage policy | map attribution control, linked to openstreetmap.org/copyright; Method page |
| Protomaps (only if self-hosted tiles are enabled; off in every current build) | basemap | Protomaps basemap terms, OSM data ODbL | map attribution control |

## Data

| Source | Used for | Terms | Credit shown |
|---|---|---|---|
| gridMET (Climatology Lab), ERC | fuel dryness, fire targets | freely available; the provider asks for the citation Abatzoglou (2013), Int. J. Climatol. 33: 121-131 | Method page |
| U.S. Drought Monitor (NDMC, USDA, NOAA) | drought categories | free to use with the NDMC credit line | Method page, full credit line |
| USGS Watershed Boundary Dataset and National Hydrography Dataset | Upper South Platte and Dillon boundaries, Strontia Springs Reservoir | U.S. public domain | Method page |
| U.S. Census Bureau 2023 cartographic boundary files | county boundaries, Denver footprint | U.S. public domain | Method page |
| SubX CFSv2 (NOAA), via the IRI Data Library | evaluated once, not used by any shipped target | NOAA data, public | Method page data list |
| ESI (SERVIR), EDDI (NOAA PSL), SNOTEL (USDA NRCS) | research arms only; nothing shipped uses them | public agency data | this file |

## Fonts

Committed in `app/fonts/` and loaded with `next/font/local`, so the build
fetches nothing. They are the latin-subset files `next/font/google` served
until 2026-10-15, byte for byte; that day Google Fonts returned font URLs
`next/font` could not parse and the site build failed, so the files were
taken from the last good build instead of fetched again. All three are under
the SIL Open Font License 1.1, which requires no on-screen credit; the
license and each family's copyright line (from the files' own name tables)
are in `app/fonts/OFL.txt`. The film (`film/`) uses the same files.

| Font | Version (name table) | Files | License |
|---|---|---|---|
| Newsreader | 1.003 | `Newsreader-latin.woff2`, `Newsreader-Italic-latin.woff2` (variable, 300 to 500) | SIL OFL 1.1 |
| Outfit | 1.100 | `Outfit-latin.woff2` (variable, 300 to 600) | SIL OFL 1.1 |
| IBM Plex Mono | 2.3 | `IBMPlexMono-Regular-latin.woff2`, `IBMPlexMono-Medium-latin.woff2` | SIL OFL 1.1 |

## Code libraries (main runtime dependencies)

Versions as installed on 2026-09-27; full lists in `app/package-lock.json` and
`uv.lock`. None requires an on-screen credit. Their license texts ship inside
the installed packages.

| Front end | License |
|---|---|
| next 14.2.35, react 18.3.1, react-dom 18.3.1 | MIT |
| maplibre-gl 4.7.1, pmtiles 4.5.0 | BSD-3-Clause |
| motion 13.4.0, zod 4.6.5, tailwindcss 3.4.19, @phosphor-icons/react 2.1.10 | MIT |
| idb-keyval 6.3.0 | Apache-2.0 |

| Python | License |
|---|---|
| numpy, pandas, geopandas, shapely, rasterio, scipy, scikit-learn, h5netcdf | BSD |
| xarray, requests, torch | Apache-2.0 |
| fastapi, sqlmodel, netCDF4, pyproj, pyogrio, lightgbm | MIT |
| arch | NCSA |

## Removed

`app/public/img/westfork.jpg` (West Fork Complex Fires near Del Norte, 2013,
U.S. Department of Agriculture, CC BY 2.0) was tracked but never shown, so it
was removed rather than credited. It remains in git history, where its CC BY
2.0 license applies.

## This repository's own license

There is no LICENSE file. Until the owner adds one, the code is all rights
reserved by default even in a public repository. Choosing a license is the
owner's decision.

## Deployed basemap (added 2026-10-12)

| What | Source | License | Credit shown |
|---|---|---|---|
| Colorado vector tiles, `colorado.pmtiles` (release asset `basemap`) | Protomaps daily build 2026-10-11, from OpenStreetMap and Natural Earth | map data ODbL (OpenStreetMap); Protomaps basemap | "© OpenStreetMap contributors · © Protomaps", on the map |
| Glyphs, Noto Sans Regular (`app/public/fonts/`) | protomaps/basemaps-assets | SIL OFL 1.1 (`app/public/fonts/OFL.txt`) | none required |
| `pmtiles` CLI 1.31.2 (tool, not shipped) | Homebrew bottle | BSD-3-Clause | none required |

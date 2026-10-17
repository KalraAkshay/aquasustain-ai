# Evidence provenance — India v2

Source: CGWB, National Compilation on Dynamic Ground Water Resources of India 2025.

https://www.jalshakti-dowr.gov.in/static/uploads/2025/11/711d8d476bbf498cd90f8038e7371227.pdf

Retrieved 11 October 2026. The snapshot source manifest records its SHA-256. The original PDF is not redistributed. Values were extracted from published tables, structurally checked and reconciled; sample pages were visually inspected. Do not claim all rows were independently human reviewed.

## Coverage

- 36 states/UTs: Annexure I, PDF page 169 (printed 143).
- 709 district entries: Annexure II, PDF pages 173–210 (printed 147–184).
- 14 named Ludhiana assessment units: category-only observations, Annexure IV(A), PDF page 383 (printed 357). All are published as Over-exploited. No unit-specific numeric extraction stage is imported.
- Ludhiana district: 194.65% extraction stage, PDF page 193 (printed 167). This district figure is never presented as a unit-specific figure.

Coverage follows the report's names and assessment geography, not a current directory of every administrative district. Several states have partial geographic assessment coverage. Search by source district name; newly reorganized districts may not appear. No parcel-to-unit mapping exists.

District volumes are converted from hectare-metres to cubic metres (×10,000); state volumes from billion cubic metres (×1,000,000,000). Extraction stage is annual total groundwater extraction / annual extractable groundwater resources ×100. A value above 100% describes aggregate reported pressure, not a facility's demand or the fraction of water remaining.

Nagapattinam, Kolkatta (source spelling), and South 24 Parganas have missing/zero-resource inputs. Their stages are stored as null and excluded from ordering, rather than treating printed zero as low pressure. Other data gaps are disclosed in the UI.

## Reproduce and review

Download the exact official report, then use an environment with `requirements-data.txt` installed:

```bash
python scripts/import_india_2025.py /path/to/report.pdf
python scripts/validate_data.py
python -m pytest -q
```

`data/extraction_audit.json` preserves original district table rows. The importer is tied to this 482-page edition; review changes before importing a new edition. Category-only Ludhiana records are visually transcribed, not inferred from district percentages.

Tests reconcile every usable district extraction ratio and each state's district volume sum against its rounded state total. These catch extraction errors, not errors in the official source. A teammate should check demonstration rows against the PDF before recording.

Same-level, same-year usable numeric records can be ordered by extraction stage. This is not an overall site-suitability score. Categories are shown only where explicitly reported. No live monitoring, water-quality measurements, pollution attribution, supply contracts, seasonal forecasts, permit decisions or depletion predictions are included. Reclaimed supply and WUE remain user assumptions.

## Navigation map

The locally bundled SVG derives from DataMeet Community Maps, States/Admin2 shapefile retrieved 12 October 2026: https://github.com/datameet/maps/tree/master/States . Attribution: DataMeet Community Maps contributors; source project https://projects.datameet.org/maps/states/ . The state-map page specifies Creative Commons Attribution 2.5 India: https://creativecommons.org/licenses/by/2.5/in/ . Geometry was simplified to 0.025 degrees and projected for a compact SVG; labels and accessible selection controls were added. It is a navigation aid, not a survey or parcel boundary authority. The map does not imply groundwater measurements at each point and has no district boundary overlay. All 36 map IDs are matched to the evidence catalogue.

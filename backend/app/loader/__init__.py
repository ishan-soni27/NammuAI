"""One-time load of the BlueTide CSV exports into the database (BUILD_PROMPT §10 layer 2, §14 Phase 2).

read_raw.py   read files as exact strings          reference.py  read data/reference seeds
normalize.py  parse dates/numbers/codes            classify.py   demand class, lifecycle
convert.py    case/pound conversion                rules.py      T01–T31, one builder per file
pipeline.py   run all rules (pure)                 write.py      store raw + clean + issues
report.py     docs/DATA_LOAD_REPORT.md             run.py        CLI: python -m app.loader.run
"""

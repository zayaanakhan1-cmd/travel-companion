# Data directory

`csc.sqlite3` is generated here at runtime by `app.geography.dataset_builder`
from the open [countries-states-cities-database](https://github.com/dr5hn/countries-states-cities-database)
(ODbL-1.0). It is **not** committed - see the "Generated geography data cache"
section of the root `.gitignore`.

Build it explicitly with:

```bash
cd backend && python -m app.geography
```

Or let the API build it on first request (`OPEN_DATASET_AUTO_BUILD=true`, the
default).

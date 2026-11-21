# Catalog capability

Owns read-only access and search/detail projections for versioned place snapshots. The JSON snapshot is the authority for place facts; this module does not own trip activities, route-provider behavior, or catalog curation. Other capabilities may call only `application.py` public queries.

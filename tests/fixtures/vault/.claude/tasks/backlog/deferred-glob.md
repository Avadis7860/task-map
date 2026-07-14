---
id: deferred-glob
status: backlog
priority: P2
depends_on: []
trigger:
  when: glob_count
  glob: "nope/**/*.md"
  op: ">="
  value: 5
---
# Objectif final
READY sauf trigger glob non franchi → DEFERRED.

Plans
-----

Design decisions:

- Use directory trees for fast dropping? No, not all FS support efficiently; Probably faster on avg to use an index file.

TODO
-----

- Thread safety
- Remove orphans

Features
----------

- 1- or 2-level cache
- lossy or non-lossy compression
- Static typing
- TTL

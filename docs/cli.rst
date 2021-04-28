CLI
===

::

   memoize [--obj-store path] [--env env] [--key key] [--ver ver] [--comparison (mtime|crc32)] [--replacement (gd-size|luv)] [--max-size '123 MiB'] [--verbose] -- command arg1 arg2 ...

The following items are matched in order.

1. ``--obj-store`` (implicitly lookup)
2. ``--env`` (match)
3. ``command`` (lookup)
4. The contents of ``command`` (match)
5. ``arg1, arg2, ...`` and ``--key`` (lookup)
6. The input files and ``--ver`` (match)

This is useful for ``memoizing`` parts of a shell-script pipeline. stdin and stdout work just like
normal files, so it can be safely used in a pipe.

``command`` may require stdin, but no TTY interactivity.

``memoize`` uses syscall interception to learn the input and output files.

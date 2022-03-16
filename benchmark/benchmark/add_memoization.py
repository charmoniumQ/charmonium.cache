import ast
import json
from pathlib import Path
from typing import Iterable, List, Sequence, cast


def add_memoization(code: Iterable[ast.stmt]) -> Sequence[ast.stmt]:
    future_imports = []
    ch_cache_imports = ast.parse("from charmonium.cache import memoize").body
    stmts = []
    for stmt in code:
        if isinstance(stmt, ast.ImportFrom):
            future_imports.append(cast(ast.stmt, stmt))
        elif isinstance(stmt, ast.FunctionDef) and stmt.name != "main":
            stmts.append(
                cast(
                    ast.stmt,
                    ast.FunctionDef(
                        name=stmt.name,
                        args=stmt.args,
                        body=stmt.body,
                        decorator_list=[
                            cast(
                                ast.expr,
                                ast.Name(id="memoize", ctx=ast.Load()),
                            )
                        ]
                        + stmt.decorator_list,
                        returns=stmt.returns,
                        type_comment=stmt.type_comment,
                    ),
                )
            )
        else:
            stmts.append(stmt)
    return future_imports + ch_cache_imports + stmts

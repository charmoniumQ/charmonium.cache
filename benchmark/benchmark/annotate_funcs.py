import ast
from copy import deepcopy
from pathlib import Path
from typing import Union, cast

stmts_with_body = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
)
stmts_with_orelse = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.Try,
)
stmts_with_finalbody = (ast.Try,)
stmts_with_handler = (ast.Try,)

# memoize = cast(ast.expr, ast.parse("memoize()", mode="eval"))
# from_charmonium_cache_import_memoize = ast.parse(
#     "from charmonium.cache import memoize"
# ).body[0]


def annotate_funcs_in_stmt(stmt: ast.stmt, decorator: ast.expr, copy: bool = False) -> ast.stmt:
    if copy:
        stmt = deepcopy(stmt)
    if isinstance(stmt, ast.FunctionDef) and not any(
        "savefig" in ast.unparse(stmt) or "self" in ast.unparse(stmt)
        for stmt in stmt.body
    ):
        stmt.decorator_list = [decorator] + stmt.decorator_list
        stmt.body = [annotate_funcs_in_stmt(stmt, decorator, copy=False) for stmt in stmt.body]
        return stmt
    else:
        if isinstance(stmt, stmts_with_body):
            stmt.body = [
                annotate_funcs_in_stmt(child_stmt, decorator, copy=False)
                for child_stmt in stmt.body
            ]
        if isinstance(stmt, stmts_with_orelse):
            stmt.orelse = [
                annotate_funcs_in_stmt(child_stmt, decorator, copy=False)
                for child_stmt in stmt.orelse
            ]
        if isinstance(stmt, stmts_with_finalbody):
            stmt.finalbody = [
                annotate_funcs_in_stmt(child_stmt, decorator, copy=False)
                for child_stmt in stmt.finalbody
            ]
        # if isinstance(stmt, stmts_with_handler):
        #     stmt.handlers = [
        #         annotate_funcs_in_stmt(handler, decorator, copy=False)
        #         for handler in stmt.handlers
        #     ]
        return cast(ast.stmt, stmt)


def annotate_funcs_in_module(module: ast.Module, decorator: ast.expr, copy: bool = False) -> ast.Module:
    if copy:
        module = deepcopy(module)
    module.body = [
        annotate_funcs_in_stmt(stmt, decorator, copy=False)
        # no need to copy, since we are already copied the whole module
        for stmt in module.body
    ]
    return module


def annotate_funcs_in_file(source: Path, decorator: ast.expr) -> None:
    source.write_text(
        ast.unparse(annotate_funcs_in_module(ast.parse(source.read_text()), decorator))
    )

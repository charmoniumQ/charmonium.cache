import ast
import bisect
import copy
import re
from typing import Any, Callable, List, Mapping, Sequence, Set, Tuple, TypeVar, Union, cast

import beniget  # type: ignore
import gast  # type: ignore
from .util import last_sentinel


def cells_to_stmts(cells: Sequence[str]) -> Tuple[Sequence[ast.stmt], Sequence[ast.FunctionDef], ast.Module]:
    # cell_reads[i] holds every variable cells[i] uses.
    cell_reads: List[Set[str]] = [set() for _ in cells]
    # cell_writes[i] holds every variable cells[i] defs.
    cell_writes: List[Set[str]] = [set() for _ in cells]

    cell_linecounts = [cell.count("\n") for cell in cells]

    def line_to_cell(lineno: int) -> int:
        accumulator = 1
        for cell_no, cell_linecount in enumerate(cell_linecounts):
            accumulator += cell_linecount
            if lineno < accumulator:
                return cell_no
        else:
            return len(cells) - 1

    cells_gast = gast.parse("".join(cells))
    duc = beniget.DefUseChains()
    duc.visit(cells_gast)

    for var in duc.locals[cells_gast]:
        if var.node.lineno is not None:
            def_cell = line_to_cell(var.node.lineno)
            for user in var.users():
                use_cell = line_to_cell(user.node.lineno)
                if use_cell != def_cell:
                    cell_writes[def_cell].add(var.name())
                    cell_reads[use_cell].add(var.name())

    imports: List[Union[ast.Import, ast.ImportFrom]] = []
    function_defs: List[ast.FunctionDef] = []
    main_function = cast(ast.FunctionDef, ast.parse("def main(): ...").body[0])
    main_function.body = []
    for i, (cell, reads, writes) in enumerate(zip(cells, cell_reads, cell_writes)):
        name = f"cell{i}"
        reads_str = ",".join(reads)
        func_def = cast(ast.FunctionDef, ast.parse(f"def {name}({reads_str}): ...").body[0])
        inner_stmts: List[ast.stmt] = []
        for stmt, is_last in last_sentinel(ast.parse(cell).body):
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                imports.append(stmt)
            elif isinstance(stmt, ast.FunctionDef):
                function_defs.append(stmt)
            elif is_last and isinstance(stmt, ast.Expr):
                inner_stmts.append(cast(ast.stmt, ast.parse(f"cell{i}_output = {ast.unparse(stmt)}")))
                inner_stmts.append(cast(ast.stmt, ast.parse(f"print(cell{i}_output)")))
            else:
                inner_stmts.append(stmt)
        if inner_stmts:
            func_def.body = inner_stmts
            function_defs.append(func_def)
            if writes:
                writes_str = ",".join(writes)
                return_stmt = ast.parse(f"return {writes_str}").body[0] if writes else None
                if return_stmt:
                    func_def.body.append(return_stmt)
                main_function.body.append(ast.parse(f"{writes_str} = {name}({reads_str})").body[0])
            else:
                main_function.body.append(ast.parse(f"{name}({reads_str})").body[0])

    main_call = ast.parse('if __name__ == "__main__":\n    main()\n')
    return imports, (*function_defs, main_function), main_call


ipython_magic = re.compile(r"^%[a-z]|^.*[?]$")
def sanitize_lines(lines: List[str]) -> List[str]:
    return [line for line in lines if not ipython_magic.match(line)]


def ipynb_to_cells(ipynb_src: Mapping[str, Any]) -> List[str]:
    cells = []
    for cell in ipynb_src["cells"]:
        if cell["cell_type"] == "code":
            cells.append("".join(sanitize_lines(cell["source"])) + "\n")
    return cells


if __name__ == "__main__":
    from pathlib import Path
    import json
    import typer
    from .annotate_funcs import annotate_funcs_in_stmt

    def main(
        in_file: typer.FileText,
        out_file: typer.FileTextWrite,
    ) -> None:
        cells = ipynb_to_cells(json.load(in_file))
        imports, functions, main_call = cells_to_stmts(cells)
        decorator = cast(ast.Expr, ast.parse("memoize(group=group)").body[0]).value
        for function in functions:
            function.decorator_list.insert(0, decorator)
        out_file.write(
            "\n".join([
                "\n".join(map(ast.unparse, imports)),
                "",
                "\n\n".join(map(ast.unparse, functions)),
                "",
                ast.unparse(main_call),
                "",
            ])
        )

    typer.run(main)

import ast
import bisect
from typing import Any, Callable, List, Mapping, Sequence, Set, TypeVar

import beniget  # type: ignore
import gast  # type: ignore


def cells_to_stmts(cells: Sequence[str]) -> Sequence[ast.stmt]:
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

    cells_ast = gast.parse("".join(cells))
    duc = beniget.DefUseChains()
    duc.visit(cells_ast)

    for var in duc.locals[cells_ast]:
        if var.node.lineno is not None:
            def_cell = line_to_cell(var.node.lineno)
            for user in var.users():
                use_cell = line_to_cell(user.node.lineno)
                if use_cell != def_cell:
                    cell_writes[def_cell].add(var.name())
                    cell_reads[use_cell].add(var.name())

    future_imports = []
    function_defs = []
    main_function = gast.parse("def main(): ...").body[0]
    main_function.body = []
    for i, (cell, reads, writes) in enumerate(zip(cells, cell_reads, cell_writes)):
        name = f"cell{i}"
        reads_str = ",".join(reads)
        writes_str = ",".join(writes)
        func_def = gast.parse(f"def {name}({reads_str}): ...").body[0]
        return_stmts = gast.parse(f"return {writes_str}").body if writes else []
        safe_stmts = []
        for stmt in gast.parse(cell).body:
            if isinstance(stmt, gast.ImportFrom) and stmt.module == "__future__":
                future_imports.append(stmt)
            else:
                safe_stmts.append(stmt)
        func_def.body = safe_stmts + return_stmts
        function_defs.append(func_def)
        main_function.body.append(
            gast.parse(
                f"{writes_str} = {name}({reads_str})"
                if writes
                else f"{name}({reads_str})"
            ).body[0]
        )
    main_function_call = gast.parse('if __name__ == "__main__":\n    main()\n').body
    return [
        gast.gast_to_ast(gast_node)
        for gast_node in future_imports
        + function_defs
        + [main_function]
        + main_function_call
    ]


def sanitize_lines(lines: List[str]) -> List[str]:
    return [line for line in lines if not line.startswith("%matplotlib")]


def ipynb_to_cells(ipynb_src: Mapping[str, Any]) -> List[str]:
    cells = []
    for cell in ipynb_src["cells"]:
        if cell["cell_type"] == "code":
            cells.append("".join(sanitize_lines(cell["source"])) + "\n")
    return cells


# def ipynb_path_to_func_code(ipynb: Path, func_code: Path) -> None:
#     func_code.write_text(
#         cells_to_func_code(
#             ipynb_to_cells(
#                 json.loads(
#                     ipynb.read_text()
#                 )
#             )
#         )
#     )


# if __name__ == "__main__":
#     from pathlib import Path
#     import json
#     import typer

#     def main(
#         in_file: typer.FileText,
#         out_file: typer.FileTextWrite,
#         out_file2: typer.FileTextWrite,
#     ) -> None:
#         cells = ipynb_to_cells(json.load(in_file))
#         out_file2.write(cells_to_func_code(cells))

#     typer.run(main)

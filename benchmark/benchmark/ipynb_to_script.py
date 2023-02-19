import ast
import bisect
import copy
import re
from typing import Any, Callable, List, Mapping, Sequence, Set, Tuple, TypeVar, Union, cast

import beniget  # type: ignore
import gast  # type: ignore
from .util import last_sentinel


def cells_to_stmts(cells: Sequence[str], suffix: str = "") -> Tuple[Sequence[ast.stmt], Sequence[ast.FunctionDef], ast.Expr]:
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
    main_function = cast(ast.FunctionDef, ast.parse(f"def main{suffix}(): ...").body[0])
    main_function.body = []
    for i, (cell, reads, writes) in enumerate(zip(cells, cell_reads, cell_writes)):
        name = f"cell{i}{suffix}"
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
                inner_stmts.append(cast(ast.stmt, ast.parse(f'if cell{i}_output is not None:\n    print("cell{i}_output", cell{i}_output)')))
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

    main_call = ast.parse(f'main{suffix}()').body[0]
    return imports, (*function_defs, main_function), main_call


ipython_magic = re.compile(r"(^%[^%].*$)|(^.*[?]$)|(^!.*$)")
ipython_inline_shell = re.compile("^(.*)(![^=]*)$")
def sanitize_lines(lines: List[str]) -> Tuple[List[str], List[str]]:
    clean_lines = []
    magic_lines = []
    for line in lines:
        if ipython_magic.match(line):
            magic_lines.append(line)
            line = ipython_magic.sub(r'""" \g<1> """', line)
        if ipython_inline_shell.match(line):
            magic_lines.append(line)
            line = ipython_inline_shell.sub(r'\g<1>[""" \g<2> """]\n', line)
        clean_lines.append(line)
    return clean_lines, magic_lines


ipython_block_magic = re.compile("(^%%.*$)")
def ipynb_to_cells(ipynb_src: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    cells = []
    magic_lines = []
    for cell in ipynb_src["cells"]:
        lines = []
        if cell["cell_type"] == "code":
            for line in cell["source"]:
                if ipython_block_magic.match(line):
                    magic_lines.append("".join(cell["source"]))
            else:
                clean_lines, this_magic_lines = sanitize_lines(cell["source"])
                magic_lines.extend(this_magic_lines)
                cells.append("".join(clean_lines) + "\n")
    return cells, magic_lines


if __name__ == "__main__":
    from pathlib import Path
    import json
    import itertools
    import typer
    from tqdm import tqdm
    from .annotate_funcs import annotate_funcs_in_stmt

    standard_boilerplate = """
from charmonium.determ_hash import determ_hash
from charmonium.freeze import freeze
from charmonium.cache import memoize, MemoizedGroup, FileContents
from pathlib import Path

group = MemoizedGroup(size="1GiB")

def print_plt(old_func):
    def new_func(*args, **kwargs):
        ret = old_func(*args, **kwargs)
        plt.savefig("/tmp/fig.raw")
        plt.close()
        plot = Path("/tmp/fig.raw").read_bytes()
        print(old_func.__name__, "plt", determ_hash(plot))
        return ret
    return new_func

def print_ret(old_func):
    def new_func(*args, **kwargs):
        ret = old_func(*args, **kwargs)
        print(old_func.__name__, determ_hash(freeze(ret)))
        return ret
    return new_func
"""

    def main(
        in_files: List[Path],
        out_file: typer.FileTextWrite,
    ) -> None:
        imports = []
        functions = []
        main_calls = []
        for in_file in tqdm(in_files, desc="files"):
            cells, magic_lines = ipynb_to_cells(json.loads(in_file.read_text()))
            for magic_line in magic_lines:
                if magic_line.startswith("%config"):
                    continue
                print("Ignoring magic:", magic_line.strip())
            this_imports, this_functions, this_main_call = cells_to_stmts(cells, suffix=f"_{in_file.stem}")
            imports.extend(this_imports)
            functions.extend(this_functions)
            main_calls.append(this_main_call)

        memoize_decorator = cast(ast.Expr, ast.parse("memoize(group=group)").body[0]).value
        print_plt_decorator = cast(ast.Expr, ast.parse("print_plt").body[0]).value
        print_ret_decorator = cast(ast.Expr, ast.parse("print_ret").body[0]).value
        for function in functions:
            function.decorator_list.insert(0, memoize_decorator)
            result = ast.unparse(function)
            if "plt." in result:
                function.decorator_list.insert(0, print_plt_decorator)
            if "return" in result:
                function.decorator_list.insert(0, print_ret_decorator)

        main_guard = ast.parse('if __name__ == "__main__":\n    pass').body[0]
        main_guard.body = main_calls

        out_file.write(
            "\n".join([
                "\n".join(set(map(ast.unparse, imports))),
                "",
                standard_boilerplate,
                "",
                "\n\n".join(map(ast.unparse, functions)),
                "",
                ast.unparse(main_guard),
                "",
            ])
        )

    typer.run(main)

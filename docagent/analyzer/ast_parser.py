"""Python AST parser extracting symbols, API endpoints, config vars, and dependencies."""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from docagent.analyzer.models import (
    APIRouteDescriptor,
    ConfigDescriptor,
    ParameterDescriptor,
    SymbolDescriptor,
    SymbolKind,
)
from docagent.core.logging import logger


class PythonASTParser:
    """Parses Python source files using standard library AST."""

    def __init__(self, rel_path: str, source_code: str):
        self.rel_path = rel_path
        self.source_code = source_code
        self.symbols: List[SymbolDescriptor] = []
        self.api_routes: List[APIRouteDescriptor] = []
        self.configs: List[ConfigDescriptor] = []
        self.imports: List[str] = []

    def parse(self) -> Tuple[List[SymbolDescriptor], List[APIRouteDescriptor], List[ConfigDescriptor], List[str]]:
        """Parses source code and extracts all descriptors."""
        try:
            tree = ast.parse(self.source_code, filename=self.rel_path)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {self.rel_path}: {e}")
            return [], [], [], []

        for node in ast.walk(tree):
            # Extract Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.imports.append(node.module)

            # Extract Environment Variables / Config
            self._extract_config_access(node)

        # Extract Classes and Functions from top-level and class-level
        self._extract_symbols_and_routes(tree)

        return self.symbols, self.api_routes, self.configs, self.imports

    def _extract_config_access(self, node: ast.AST) -> None:
        """Detects os.environ.get(), os.getenv() calls."""
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                # os.getenv(...) or os.environ.get(...)
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    func_name = f"os.{node.func.attr}"
                elif (
                    isinstance(node.func.value, ast.Attribute)
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == "os"
                    and node.func.value.attr == "environ"
                ):
                    func_name = f"os.environ.{node.func.attr}"

            if func_name in ("os.getenv", "os.environ.get") and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    key_name = first_arg.value
                    default_val = None
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        default_val = str(node.args[1].value)
                    
                    self.configs.append(
                        ConfigDescriptor(
                            key=key_name,
                            source_file=self.rel_path,
                            default_value=default_val,
                            is_secret=any(term in key_name.lower() for term in ("key", "secret", "token", "password")),
                        )
                    )

    def _extract_symbols_and_routes(self, tree: ast.Module) -> None:
        """Traverses the AST module to record classes, functions, and API route decorators."""
        # Also traverse any nested functions (e.g. routes declared inside create_app)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in node.decorator_list:
                    self._check_api_route(d, node.name, node.lineno)

        for item in tree.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process_function(item)
            elif isinstance(item, ast.ClassDef):
                self._process_class(item)

    def _process_function(
        self,
        node: ast.AST,
        parent_class: Optional[str] = None
    ) -> SymbolDescriptor:
        """Processes a FunctionDef or AsyncFunctionDef node."""
        func_name = getattr(node, "name", "")
        qualified_name = f"{parent_class}.{func_name}" if parent_class else func_name
        is_method = parent_class is not None
        kind = SymbolKind.METHOD if is_method else SymbolKind.FUNCTION
        is_async = isinstance(node, ast.AsyncFunctionDef)
        docstring = ast.get_docstring(node)

        # Extract arguments
        parameters: List[ParameterDescriptor] = []
        args_obj = node.args
        defaults_offset = len(args_obj.args) - len(args_obj.defaults)

        for i, arg in enumerate(args_obj.args):
            arg_name = arg.arg
            type_str = ast.unparse(arg.annotation) if arg.annotation else None
            
            default_val_str = None
            if i >= defaults_offset:
                def_idx = i - defaults_offset
                if def_idx < len(args_obj.defaults):
                    default_val_str = ast.unparse(args_obj.defaults[def_idx])

            parameters.append(
                ParameterDescriptor(
                    name=arg_name,
                    type_annotation=type_str,
                    default_value=default_val_str,
                    is_optional=(default_val_str is not None),
                )
            )

        # Extract return type
        return_type = ast.unparse(node.returns) if node.returns else None

        # Extract decorators
        decorators: List[str] = []
        for d in node.decorator_list:
            dec_str = ast.unparse(d)
            decorators.append(dec_str)
            # Check for API route decorator: @app.get(...), @router.post(...), @api.route(...)
            self._check_api_route(d, func_name, node.lineno)

        symbol = SymbolDescriptor(
            name=func_name,
            qualified_name=qualified_name,
            kind=kind,
            file_path=self.rel_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=docstring,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            is_exported=not func_name.startswith("_"),
            is_async=is_async,
            parent_class=parent_class,
        )
        self.symbols.append(symbol)
        return symbol

    def _process_class(self, node: ast.ClassDef) -> SymbolDescriptor:
        """Processes a ClassDef node and its inner methods."""
        class_name = node.name
        docstring = ast.get_docstring(node)
        bases = [ast.unparse(b) for b in node.bases]
        decorators = [ast.unparse(d) for d in node.decorator_list]

        class_symbol = SymbolDescriptor(
            name=class_name,
            qualified_name=class_name,
            kind=SymbolKind.CLASS,
            file_path=self.rel_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=docstring,
            decorators=decorators,
            is_exported=not class_name.startswith("_"),
            return_type=f"class({', '.join(bases)})" if bases else "class",
        )
        self.symbols.append(class_symbol)

        # Process methods and settings attributes inside class
        is_settings_class = any("settings" in b.lower() for b in bases)
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process_function(item, parent_class=class_name)
            elif is_settings_class and isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                key_name = item.target.id
                default_val = ast.unparse(item.value) if item.value else None
                self.configs.append(
                    ConfigDescriptor(
                        key=key_name,
                        source_file=self.rel_path,
                        default_value=default_val,
                        is_secret=any(term in key_name.lower() for term in ("key", "secret", "token", "password")),
                    )
                )

        return class_symbol

    def _check_api_route(self, dec_node: ast.AST, handler_name: str, line_no: int) -> None:
        """Parses route decorators like @router.get('/path') or @app.post('/items')."""
        if not isinstance(dec_node, ast.Call):
            return

        method = None
        if isinstance(dec_node.func, ast.Attribute):
            attr_name = dec_node.func.attr.upper()
            if attr_name in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
                method = attr_name

        if method and dec_node.args:
            route_path_node = dec_node.args[0]
            if isinstance(route_path_node, ast.Constant) and isinstance(route_path_node.value, str):
                route_path = route_path_node.value
                if not any(r.http_method == method and r.path == route_path and r.line_number == line_no for r in self.api_routes):
                    self.api_routes.append(
                        APIRouteDescriptor(
                            http_method=method,
                            path=route_path,
                            handler_name=handler_name,
                            file_path=self.rel_path,
                            line_number=line_no,
                        )
                    )

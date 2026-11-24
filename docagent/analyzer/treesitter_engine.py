"""Tree-sitter parser extracting symbols and routes from JavaScript and TypeScript."""

from pathlib import Path
from typing import List, Optional, Tuple

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from docagent.analyzer.models import (
    APIRouteDescriptor,
    ConfigDescriptor,
    ParameterDescriptor,
    SymbolDescriptor,
    SymbolKind,
)
from docagent.core.logging import logger


class TreeSitterEngine:
    """Parses JavaScript and TypeScript files using Tree-sitter AST queries."""

    def __init__(self):
        # Initialize languages and parsers
        try:
            self.js_language = Language(tsjs.language())
            self.js_parser = Parser(self.js_language)

            self.ts_language = Language(tsts.language_typescript())
            self.ts_parser = Parser(self.ts_language)
        except Exception as e:
            logger.error(f"Failed to initialize Tree-sitter languages: {e}")
            raise

    def parse_file(
        self,
        rel_path: str,
        source_code: str,
        language: str = "javascript"
    ) -> Tuple[List[SymbolDescriptor], List[APIRouteDescriptor], List[ConfigDescriptor], List[str]]:
        """Parses JS/TS file and extracts code descriptors."""
        parser = self.ts_parser if language == "typescript" else self.js_parser
        source_bytes = source_code.encode("utf-8")
        
        try:
            tree = parser.parse(source_bytes)
        except Exception as e:
            logger.warning(f"Tree-sitter parse failed for {rel_path}: {e}")
            return [], [], [], []

        symbols: List[SymbolDescriptor] = []
        api_routes: List[APIRouteDescriptor] = []
        configs: List[ConfigDescriptor] = []
        imports: List[str] = []

        self._walk_node(
            tree.root_node,
            source_bytes,
            rel_path,
            symbols,
            api_routes,
            configs,
            imports
        )

        return symbols, api_routes, configs, imports

    def _walk_node(
        self,
        node: Node,
        source_bytes: bytes,
        rel_path: str,
        symbols: List[SymbolDescriptor],
        api_routes: List[APIRouteDescriptor],
        configs: List[ConfigDescriptor],
        imports: List[str],
        parent_class: Optional[str] = None
    ) -> None:
        """Recursive node visitor for AST."""
        node_type = node.type

        # 1. Imports
        if node_type in ("import_statement", "import_declaration"):
            module_name = self._extract_import_source(node, source_bytes)
            if module_name:
                imports.append(module_name)

        # 2. Config / Environment variables: process.env.VAR_NAME
        elif node_type == "member_expression":
            text = node.text.decode("utf-8", errors="ignore")
            if text.startswith("process.env."):
                var_name = text.split("process.env.")[1].split(".")[0].split(";")[0].strip()
                if var_name:
                    configs.append(
                        ConfigDescriptor(
                            key=var_name,
                            source_file=rel_path,
                            is_secret=any(term in var_name.lower() for term in ("key", "secret", "token", "pass")),
                        )
                    )

        # 3. Class Declaration
        elif node_type in ("class_declaration", "class"):
            class_name = self._get_node_name(node, source_bytes) or "AnonymousClass"
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            symbol = SymbolDescriptor(
                name=class_name,
                qualified_name=class_name,
                kind=SymbolKind.CLASS,
                file_path=rel_path,
                start_line=start_line,
                end_line=end_line,
                is_exported=self._is_exported(node),
            )
            symbols.append(symbol)

            # Walk class body
            for child in node.children:
                if child.type == "class_body":
                    for member in child.children:
                        self._walk_node(
                            member, source_bytes, rel_path, symbols, api_routes, configs, imports, parent_class=class_name
                        )
            return

        # 4. Interface Declaration (TypeScript)
        elif node_type == "interface_declaration":
            interface_name = self._get_node_name(node, source_bytes) or "AnonymousInterface"
            symbol = SymbolDescriptor(
                name=interface_name,
                qualified_name=interface_name,
                kind=SymbolKind.INTERFACE,
                file_path=rel_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                is_exported=self._is_exported(node),
            )
            symbols.append(symbol)

        # 5. Function Declaration / Method Definition
        elif node_type in ("function_declaration", "method_definition"):
            func_name = self._get_node_name(node, source_bytes)
            if func_name:
                qualified_name = f"{parent_class}.{func_name}" if parent_class else func_name
                kind = SymbolKind.METHOD if parent_class else SymbolKind.FUNCTION
                params = self._extract_parameters(node, source_bytes)

                symbol = SymbolDescriptor(
                    name=func_name,
                    qualified_name=qualified_name,
                    kind=kind,
                    file_path=rel_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parameters=params,
                    parent_class=parent_class,
                    is_exported=self._is_exported(node),
                )
                symbols.append(symbol)

        # 6. Arrow Function assigned to const: const handler = (req, res) => ...
        elif node_type == "lexical_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    var_name = self._get_node_name(child, source_bytes)
                    value_node = child.child_by_field_name("value")
                    if value_node and value_node.type == "arrow_function":
                        params = self._extract_parameters(value_node, source_bytes)
                        symbol = SymbolDescriptor(
                            name=var_name or "anonymous",
                            qualified_name=var_name or "anonymous",
                            kind=SymbolKind.FUNCTION,
                            file_path=rel_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            parameters=params,
                            is_exported=self._is_exported(node),
                        )
                        symbols.append(symbol)

        # 7. Express API Routes: app.get('/users', ...), router.post('/login', ...)
        elif node_type == "call_expression":
            self._check_express_route(node, source_bytes, rel_path, api_routes)

        # Recurse children
        for child in node.children:
            self._walk_node(
                child, source_bytes, rel_path, symbols, api_routes, configs, imports, parent_class=parent_class
            )

    def _get_node_name(self, node: Node, source_bytes: bytes) -> Optional[str]:
        """Extracts identifier name from a node."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode("utf-8", errors="ignore")
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8", errors="ignore")
        return None

    def _is_exported(self, node: Node) -> bool:
        """Determines if a node is exported via export keyword."""
        parent = node.parent
        if parent and parent.type in ("export_statement", "export_declaration"):
            return True
        return False

    def _extract_parameters(self, node: Node, source_bytes: bytes) -> List[ParameterDescriptor]:
        """Extracts function parameter list."""
        params_node = node.child_by_field_name("parameters")
        params: List[ParameterDescriptor] = []
        if not params_node:
            return params

        for child in params_node.children:
            if child.type in ("identifier", "required_parameter", "optional_parameter"):
                pname = child.text.decode("utf-8", errors="ignore")
                params.append(ParameterDescriptor(name=pname))
        return params

    def _extract_import_source(self, node: Node, source_bytes: bytes) -> Optional[str]:
        """Extracts module path from import statement."""
        source_node = node.child_by_field_name("source")
        if source_node:
            text = source_node.text.decode("utf-8", errors="ignore")
            return text.strip("'\"")
        return None

    def _check_express_route(
        self,
        node: Node,
        source_bytes: bytes,
        rel_path: str,
        api_routes: List[APIRouteDescriptor]
    ) -> None:
        """Detects Express route patterns: app.get('/path', handler)."""
        func_child = node.child_by_field_name("function")
        if func_child and func_child.type == "member_expression":
            obj_node = func_child.child_by_field_name("object")
            obj_name = obj_node.text.decode("utf-8", errors="ignore").lower() if obj_node else ""
            if obj_name not in ("app", "router", "server", "api", "route"):
                return

            property_node = func_child.child_by_field_name("property")
            if property_node:
                method = property_node.text.decode("utf-8", errors="ignore").upper()
                if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    args_node = node.child_by_field_name("arguments")
                    if args_node and len(args_node.children) > 1:
                        # First argument is typically the path string
                        path_candidate = args_node.children[1]
                        if path_candidate.type == "string":
                            route_path = path_candidate.text.decode("utf-8", errors="ignore").strip("'\"")
                            api_routes.append(
                                APIRouteDescriptor(
                                    http_method=method,
                                    path=route_path,
                                    handler_name="express_handler",
                                    file_path=rel_path,
                                    line_number=node.start_point[0] + 1,
                                )
                            )

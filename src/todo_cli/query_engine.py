"""
Enhanced Query Engine for Todo CLI

This module provides advanced search and filtering capabilities with a flexible
query syntax supporting complex filtering, logical operators, and field-specific searches.
"""

import os
import re
import yaml
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum
from typing import Any, List, Optional, Union, Dict, Callable
from fnmatch import fnmatch

from .todo import Todo, Priority, TodoStatus


class TokenType(Enum):
    """Token types for query lexical analysis"""
    FIELD = "FIELD"          # field:value
    TEXT = "TEXT"            # quoted or unquoted text
    AND = "AND"              # AND
    OR = "OR"                # OR  
    NOT = "NOT"              # NOT, -
    LPAREN = "LPAREN"        # (
    RPAREN = "RPAREN"        # )
    COMPARISON = "COMPARISON" # >, <, >=, <=
    RANGE = "RANGE"          # ..
    COMMA = "COMMA"          # ,
    SORT = "SORT"            # sort:
    EOF = "EOF"              # End of input


@dataclass
class Token:
    """A token in the query"""
    type: TokenType
    value: str
    position: int


class QueryLexer:
    """Tokenizes query strings into tokens"""
    
    def __init__(self, query: str):
        self.query = query
        self.position = 0
        self.tokens = []
        
    def tokenize(self) -> List[Token]:
        """Convert query string to tokens"""
        self.position = 0
        self.tokens = []
        
        while self.position < len(self.query):
            self._skip_whitespace()
            
            if self.position >= len(self.query):
                break
                
            char = self.query[self.position]
            
            if char == '(':
                self.tokens.append(Token(TokenType.LPAREN, char, self.position))
                self.position += 1
            elif char == ')':
                self.tokens.append(Token(TokenType.RPAREN, char, self.position))
                self.position += 1
            elif char == ',':
                self.tokens.append(Token(TokenType.COMMA, char, self.position))
                self.position += 1
            elif char == '-' and self._peek_next().isalpha():
                # Negative operator (NOT shorthand)
                self.tokens.append(Token(TokenType.NOT, char, self.position))
                self.position += 1
            elif char in '<>':
                # Comparison operators
                comp = self._read_comparison()
                self.tokens.append(Token(TokenType.COMPARISON, comp, self.position - len(comp)))
            elif char == '"':
                # Quoted text
                text = self._read_quoted_string()
                self.tokens.append(Token(TokenType.TEXT, text, self.position - len(text) - 2))
            else:
                # Field:value or text
                word = self._read_word()
                if ':' in word and not word.startswith('@'):
                    # Field query
                    self.tokens.append(Token(TokenType.FIELD, word, self.position - len(word)))
                elif word.upper() == 'AND':
                    self.tokens.append(Token(TokenType.AND, word, self.position - len(word)))
                elif word.upper() == 'OR':
                    self.tokens.append(Token(TokenType.OR, word, self.position - len(word)))
                elif word.upper() == 'NOT':
                    self.tokens.append(Token(TokenType.NOT, word, self.position - len(word)))
                elif '..' in word:
                    # Range
                    self.tokens.append(Token(TokenType.RANGE, word, self.position - len(word)))
                else:
                    # Regular text
                    self.tokens.append(Token(TokenType.TEXT, word, self.position - len(word)))
        
        self.tokens.append(Token(TokenType.EOF, '', self.position))
        return self.tokens
    
    def _skip_whitespace(self):
        """Skip whitespace characters"""
        while self.position < len(self.query) and self.query[self.position].isspace():
            self.position += 1
    
    def _peek_next(self, offset: int = 1) -> str:
        """Peek at next character"""
        pos = self.position + offset
        return self.query[pos] if pos < len(self.query) else ''
    
    def _read_comparison(self) -> str:
        """Read comparison operator (>, <, >=, <=)"""
        start = self.position
        if self._peek_next(0) in '<>' and self._peek_next(1) == '=':
            self.position += 2
            return self.query[start:self.position]
        else:
            self.position += 1
            return self.query[start:self.position]
    
    def _read_quoted_string(self) -> str:
        """Read quoted string"""
        self.position += 1  # Skip opening quote
        start = self.position
        
        while self.position < len(self.query) and self.query[self.position] != '"':
            if self.query[self.position] == '\\\\':
                self.position += 2  # Skip escaped character
            else:
                self.position += 1
        
        text = self.query[start:self.position]
        if self.position < len(self.query):
            self.position += 1  # Skip closing quote
        
        return text
    
    def _read_word(self) -> str:
        """Read a word (non-whitespace sequence)"""
        start = self.position
        
        while (self.position < len(self.query) and 
               not self.query[self.position].isspace() and
               self.query[self.position] not in '()'):
            self.position += 1
        
        return self.query[start:self.position]


class QueryNode(ABC):
    """Abstract base class for query AST nodes"""
    
    @abstractmethod
    def evaluate(self, todo: Todo) -> bool:
        """Evaluate this node against a todo"""
        pass


@dataclass
class FieldQuery(QueryNode):
    """A field-specific query (e.g., priority:high)"""
    field: str
    operator: str  # '=', '>', '<', '>=', '<=', '~', 'has', 'missing'
    value: Any
    
    def evaluate(self, todo: Todo) -> bool:
        """Evaluate field query against todo"""
        field_value = self._get_field_value(todo, self.field)
        
        if self.operator == '=':
            return self._equals_match(field_value, self.value)
        elif self.operator == '~':
            return self._pattern_match(field_value, self.value)
        elif self.operator == 'has':
            return field_value is not None and field_value != []
        elif self.operator == 'missing':
            return field_value is None or field_value == []
        elif self.operator in ['>', '<', '>=', '<=']:
            return self._numeric_compare(field_value, self.value, self.operator)
        elif self.operator == 'range':
            return self._range_match(field_value, self.value)
        elif self.operator == 'in':
            return self._in_match(field_value, self.value)
        
        return False
    
    def _get_field_value(self, todo: Todo, field: str) -> Any:
        """Get field value from todo"""
        field_map = {
            'text': todo.text,
            'priority': todo.priority.value if todo.priority else None,
            'status': todo.status.value if todo.status else None,
            'project': todo.project,
            'tags': todo.tags,
            'context': todo.context,
            'assignee': todo.assignees,
            'assignees': todo.assignees,
            'stakeholder': todo.stakeholders,
            'stakeholders': todo.stakeholders,
            'due': todo.due_date,
            'due-date': todo.due_date,
            'created': todo.created,
            'estimate': todo.time_estimate,
            'effort': todo.effort,
            'energy': todo.energy_level,
            'waiting-for': todo.waiting_for,
            'pinned': todo.pinned,
            'completed': todo.completed,
            'overdue': todo.is_overdue(),
            'active': todo.is_active(),
            'id': todo.id,
        }
        
        return field_map.get(field)
    
    def _equals_match(self, field_value: Any, query_value: Any) -> bool:
        """Check if field value equals query value"""
        if field_value is None:
            return False
            
        if isinstance(field_value, list):
            return query_value in field_value
        
        if isinstance(field_value, date) and isinstance(query_value, str):
            # Handle date comparisons
            query_date = self._parse_date(query_value)
            if query_date:
                return field_value == query_date
        
        return str(field_value).lower() == str(query_value).lower()
    
    def _pattern_match(self, field_value: Any, pattern: str) -> bool:
        """Check if field value matches pattern (wildcards)"""
        if field_value is None:
            return False
        
        if isinstance(field_value, list):
            return any(fnmatch(str(item).lower(), pattern.lower()) for item in field_value)
        
        return fnmatch(str(field_value).lower(), pattern.lower())
    
    def _numeric_compare(self, field_value: Any, query_value: Any, operator: str) -> bool:
        """Compare numeric values"""
        if field_value is None:
            return False
        
        try:
            field_num = float(field_value)
            query_num = float(query_value)
            
            if operator == '>':
                return field_num > query_num
            elif operator == '<':
                return field_num < query_num
            elif operator == '>=':
                return field_num >= query_num
            elif operator == '<=':
                return field_num <= query_num
        except (ValueError, TypeError):
            return False
        
        return False
    
    def _range_match(self, field_value: Any, range_value: tuple) -> bool:
        """Check if field value is within range"""
        if field_value is None:
            return False
        
        start, end = range_value
        
        if isinstance(field_value, (date, datetime)):
            start_date = self._parse_date(start) if isinstance(start, str) else start
            end_date = self._parse_date(end) if isinstance(end, str) else end
            
            if start_date and end_date:
                field_date = field_value.date() if isinstance(field_value, datetime) else field_value
                return start_date <= field_date <= end_date
        
        try:
            field_num = float(field_value)
            start_num = float(start)
            end_num = float(end)
            return start_num <= field_num <= end_num
        except (ValueError, TypeError):
            pass
        
        return False
    
    def _in_match(self, field_value: Any, values: list) -> bool:
        """Check if field value is in list of values"""
        if field_value is None:
            return False
        
        if isinstance(field_value, list):
            return any(item in values for item in field_value)
        
        return field_value in values
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object"""
        # This would use the existing date parsing logic from parser.py
        # For now, basic implementation
        if date_str == 'today':
            return date.today()
        elif date_str == 'tomorrow':
            from datetime import timedelta
            return date.today() + timedelta(days=1)
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None


@dataclass 
class TextQuery(QueryNode):
    """A text search query"""
    text: str
    
    def evaluate(self, todo: Todo) -> bool:
        """Evaluate text query against todo"""
        search_text = self.text.lower()
        todo_text = todo.text.lower()
        
        # Simple text search - could be enhanced with fuzzy matching
        return search_text in todo_text


@dataclass
class BinaryOp(QueryNode):
    """Binary operation (AND, OR)"""
    left: QueryNode
    operator: str  # 'AND', 'OR'
    right: QueryNode
    
    def evaluate(self, todo: Todo) -> bool:
        """Evaluate binary operation"""
        if self.operator == 'AND':
            return self.left.evaluate(todo) and self.right.evaluate(todo)
        elif self.operator == 'OR':
            return self.left.evaluate(todo) or self.right.evaluate(todo)
        return False


@dataclass
class UnaryOp(QueryNode):
    """Unary operation (NOT)"""
    operator: str  # 'NOT'
    operand: QueryNode
    
    def evaluate(self, todo: Todo) -> bool:
        """Evaluate unary operation"""
        if self.operator == 'NOT':
            return not self.operand.evaluate(todo)
        return False


class QueryParser:
    """Parses query tokens into an AST"""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.position = 0
    
    def parse(self) -> QueryNode:
        """Parse tokens into query AST"""
        if not self.tokens or len(self.tokens) <= 1:  # Only EOF
            return TextQuery("")  # Empty query matches all
        
        return self._parse_or()
    
    def _current_token(self) -> Token:
        """Get current token"""
        return self.tokens[self.position] if self.position < len(self.tokens) else self.tokens[-1]
    
    def _consume(self, expected_type: Optional[TokenType] = None) -> Token:
        """Consume current token"""
        token = self._current_token()
        if expected_type and token.type != expected_type:
            raise ValueError(f"Expected {expected_type}, got {token.type}")
        
        if self.position < len(self.tokens) - 1:
            self.position += 1
        
        return token
    
    def _parse_or(self) -> QueryNode:
        """Parse OR expression"""
        left = self._parse_and()
        
        while self._current_token().type == TokenType.OR:
            self._consume(TokenType.OR)
            right = self._parse_and()
            left = BinaryOp(left, 'OR', right)
        
        return left
    
    def _parse_and(self) -> QueryNode:
        """Parse AND expression"""
        left = self._parse_not()
        
        while (self._current_token().type in [TokenType.AND, TokenType.FIELD, TokenType.TEXT, TokenType.LPAREN] and
               self._current_token().type != TokenType.EOF):
            # Handle implicit AND
            if self._current_token().type == TokenType.AND:
                self._consume(TokenType.AND)
            
            if self._current_token().type == TokenType.EOF:
                break
                
            right = self._parse_not()
            left = BinaryOp(left, 'AND', right)
        
        return left
    
    def _parse_not(self) -> QueryNode:
        """Parse NOT expression"""
        if self._current_token().type == TokenType.NOT:
            self._consume(TokenType.NOT)
            operand = self._parse_primary()
            return UnaryOp('NOT', operand)
        
        return self._parse_primary()
    
    def _parse_primary(self) -> QueryNode:
        """Parse primary expression"""
        token = self._current_token()
        
        if token.type == TokenType.LPAREN:
            self._consume(TokenType.LPAREN)
            node = self._parse_or()
            self._consume(TokenType.RPAREN)
            return node
        elif token.type == TokenType.FIELD:
            return self._parse_field_query()
        elif token.type == TokenType.TEXT:
            text = self._consume(TokenType.TEXT).value
            return TextQuery(text)
        else:
            raise ValueError(f"Unexpected token: {token.type}")
    
    def _parse_field_query(self) -> QueryNode:
        """Parse field query"""
        field_token = self._consume(TokenType.FIELD)
        field_parts = field_token.value.split(':', 1)
        field_name = field_parts[0]
        field_value = field_parts[1] if len(field_parts) > 1 else ""
        
        # Handle special field syntaxes
        if field_name == 'has':
            return FieldQuery(field_value, 'has', None)
        elif field_name == 'missing':
            return FieldQuery(field_value, 'missing', None)
        elif field_name == 'is':
            return self._parse_special_field(field_value)
        
        # Handle value with operators
        if field_value.startswith(('>', '<')):
            operator = '>' if field_value.startswith('>') else '<'
            if field_value.startswith('>=') or field_value.startswith('<='):
                operator += '='
                value = field_value[2:]
            else:
                value = field_value[1:]
            return FieldQuery(field_name, operator, value)
        elif '..' in field_value:
            # Range query
            parts = field_value.split('..', 1)
            return FieldQuery(field_name, 'range', (parts[0], parts[1]))
        elif ',' in field_value:
            # Multiple values (OR)
            values = [v.strip() for v in field_value.split(',')]
            return FieldQuery(field_name, 'in', values)
        else:
            # Simple equality
            return FieldQuery(field_name, '=', field_value)
    
    def _parse_special_field(self, special: str) -> QueryNode:
        """Parse special field queries (is:overdue, etc.)"""
        if special == 'overdue':
            return FieldQuery('overdue', '=', True)
        elif special == 'completed':
            return FieldQuery('completed', '=', True)
        elif special == 'pinned':
            return FieldQuery('pinned', '=', True)
        elif special == 'active':
            return FieldQuery('active', '=', True)
        elif special == 'today':
            return FieldQuery('due', '=', 'today')
        else:
            return FieldQuery(special, 'has', None)


class QueryEngine:
    """Main query execution engine"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.saved_queries: Dict[str, str] = {}
        self.config_dir = config_dir or os.path.expanduser("~/.todo")
        self.queries_file = os.path.join(self.config_dir, "saved_queries.yaml")
        self._load_saved_queries()
    
    def search(self, todos: List[Todo], query: str) -> List[Todo]:
        """Execute search query against todos"""
        if not query.strip():
            return todos
        
        # Handle saved query shortcuts
        if query.startswith('@'):
            saved_name = query[1:]
            if saved_name in self.saved_queries:
                query = self.saved_queries[saved_name]
            else:
                raise ValueError(f"Saved query '{saved_name}' not found")
        
        try:
            # Tokenize
            lexer = QueryLexer(query)
            tokens = lexer.tokenize()
            
            # Parse
            parser = QueryParser(tokens)
            ast = parser.parse()
            
            # Execute
            results = []
            for todo in todos:
                if ast.evaluate(todo):
                    results.append(todo)
            
            return results
            
        except Exception as e:
            raise ValueError(f"Query error: {e}")
    
    def save_query(self, name: str, query: str):
        """Save a query for later use"""
        self.saved_queries[name] = query
        self._save_queries_to_file()
    
    def delete_query(self, name: str) -> bool:
        """Delete a saved query"""
        if name in self.saved_queries:
            del self.saved_queries[name]
            self._save_queries_to_file()
            return True
        return False
    
    def list_saved_queries(self) -> Dict[str, str]:
        """List all saved queries"""
        return self.saved_queries.copy()
    
    def _load_saved_queries(self):
        """Load saved queries from file"""
        try:
            if os.path.exists(self.queries_file):
                with open(self.queries_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict):
                        self.saved_queries = data
        except Exception:
            # If loading fails, start with empty queries
            self.saved_queries = {}
    
    def _save_queries_to_file(self):
        """Save queries to file"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.queries_file, 'w') as f:
                yaml.dump(self.saved_queries, f, default_flow_style=False)
        except Exception:
            # Silently fail - we don't want to crash on save issues
            pass

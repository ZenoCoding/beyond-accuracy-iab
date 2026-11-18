# Pure parser and evaluator extracted unchanged from repository source for standalone reproduction.
from __future__ import annotations
import re
import itertools

ROLES = {'knight', 'knave', 'spy'}
TOKEN = re.compile('[A-Za-z_][A-Za-z0-9_-]*|\\d+|[(),;]')

class CompactParseError(ValueError):
    pass

class _Parser:

    def __init__(self, text: str):
        self.tokens = TOKEN.findall(text)
        compact = ''.join(self.tokens)
        if re.sub('\\s+', '', text) != compact:
            raise CompactParseError('claim contains unsupported characters')
        self.position = 0

    def pop(self, expected: str | None=None) -> str:
        if self.position >= len(self.tokens):
            raise CompactParseError('unexpected end of claim')
        value = self.tokens[self.position]
        self.position += 1
        if expected is not None and value != expected:
            raise CompactParseError('expected %s, found %s' % (expected, value))
        return value

    def expression(self) -> dict[str, Any] | None:
        name = self.pop().upper()
        if name == 'ABSTAIN':
            return None
        self.pop('(')
        if name == 'ROLE':
            player = self.player()
            self.pop(',')
            role = self.pop().lower()
            if role not in ROLES:
                raise CompactParseError('unknown role: %s' % role)
            result: dict[str, Any] = {'op': 'role_is', 'player': player, 'role': role}
        elif name == 'STMT_TRUE':
            result = {'op': 'statement_true', 'player': self.player()}
        elif name == 'SAME_ROLE':
            left = self.player()
            self.pop(',')
            result = {'op': 'same_role', 'players': [left, self.player()]}
        elif name == 'NOT':
            result = {'op': 'not', 'arg': self.expression()}
            if result['arg'] is None:
                raise CompactParseError('NOT cannot contain ABSTAIN')
        elif name in {'AND', 'OR', 'XOR', 'IFF', 'IMPLIES'}:
            values = [self.expression()]
            while self.tokens[self.position] in {';', ','}:
                self.pop()
                values.append(self.expression())
            if len(values) < 2 or any((value is None for value in values)):
                raise CompactParseError('compound expressions require at least two non-ABSTAIN claims')
            if name == 'IMPLIES' and len(values) != 2:
                raise CompactParseError('IMPLIES requires exactly two claims')
            result = values[0]
            for value in values[1:]:
                result = {'op': name.lower(), 'left': result, 'right': value}
        elif name == 'PARITY':
            parity = self.pop().lower()
            if parity not in {'even', 'odd'}:
                raise CompactParseError('unknown parity: %s' % parity)
            self.pop(',')
            role = self.pop().lower()
            if role not in ROLES:
                raise CompactParseError('unknown parity role: %s' % role)
            players = []
            while self.tokens[self.position] != ')':
                self.pop(',')
                players.append(self.player())
            result = {'op': 'parity', 'players': players, 'role': role, 'parity': parity}
        elif name == 'COUNT':
            comparison = self.pop().lower()
            if comparison == 'at' and self.position < len(self.tokens):
                qualifier = self.pop().lower()
                if qualifier not in {'least', 'most'}:
                    raise CompactParseError('unknown count comparison: at %s' % qualifier)
                comparison = 'at_%s' % qualifier
            comparison = {'atleast': 'at_least', 'atmost': 'at_most'}.get(comparison, comparison)
            if comparison not in {'exactly', 'at_least', 'at_most'}:
                raise CompactParseError('unknown count comparison: %s' % comparison)
            self.pop(',')
            count = int(self.pop())
            self.pop(',')
            role = self.pop().lower()
            if role not in ROLES:
                raise CompactParseError('unknown count role: %s' % role)
            players = []
            while self.tokens[self.position] != ')':
                self.pop(',')
                players.append(self.player())
            result = {'op': 'count_role', 'players': players, 'role': role, 'comparison': comparison, 'count': count}
        else:
            raise CompactParseError('unknown claim operator: %s' % name)
        self.pop(')')
        return result

    def player(self) -> int:
        player = self.pop().upper()
        if len(player) != 1 or not 'A' <= player <= 'Z':
            raise CompactParseError('unknown player: %s' % player)
        return ord(player) - ord('A')

def parse_compact_expression(text: str) -> dict[str, Any] | None:
    parser = _Parser(text.strip())
    try:
        value = parser.expression()
    except IndexError as exc:
        raise CompactParseError('unexpected end of claim') from exc
    if parser.position != len(parser.tokens):
        raise CompactParseError('unexpected trailing claim tokens')
    return value

def assignments(player_count: int) -> Iterable[Assignment]:
    """Enumerate assignments satisfying the disclosed exactly-one-spy hint."""
    for spy in range(player_count):
        for non_spies in itertools.product(('knight', 'knave'), repeat=player_count - 1):
            values = iter(non_spies)
            yield tuple(('spy' if i == spy else next(values) for i in range(player_count)))

def evaluate_expr(expr: Expr, assignment: Assignment, statements: Sequence[Expr] | None=None, memo: dict[int, bool] | None=None) -> bool:
    op = expr['op']
    if op == 'role_is':
        return assignment[expr['player']] == expr['role']
    if op == 'same_role':
        (a, b) = expr['players']
        return assignment[a] == assignment[b]
    if op in {'count_role', 'parity'}:
        count = sum((assignment[p] == expr['role'] for p in expr['players']))
        if op == 'parity':
            return count % 2 == (0 if expr['parity'] == 'even' else 1)
        comparison = expr['comparison']
        target = expr['count']
        return {'exactly': count == target, 'at_least': count >= target, 'at_most': count <= target}[comparison]
    if op == 'statement_true':
        if statements is None:
            raise ValueError('statement_true requires puzzle context')
        memo = memo if memo is not None else {}
        player = expr['player']
        if player not in memo:
            memo[player] = evaluate_expr(statements[player], assignment, statements, memo)
        return memo[player]
    if op == 'not':
        return not evaluate_expr(expr['arg'], assignment, statements, memo)
    if op in {'and', 'or', 'xor', 'iff', 'implies'}:
        left = evaluate_expr(expr['left'], assignment, statements, memo)
        right = evaluate_expr(expr['right'], assignment, statements, memo)
        if op == 'and':
            return left and right
        if op == 'or':
            return left or right
        if op == 'xor':
            return left != right
        if op == 'iff':
            return left == right
        return not left or right
    raise ValueError(f'unknown expression operator: {op}')

def contains_role_predicate(expression):
    """True for an explicit role_is atom, including inside a compound formula."""
    if isinstance(expression, dict):
        return expression.get("op") == "role_is" or any(
            contains_role_predicate(value) for value in expression.values()
        )
    if isinstance(expression, (list, tuple)):
        return any(contains_role_predicate(value) for value in expression)
    return False


def unique_index(rows, key_fields, label):
    """Reject duplicate identities before indexing can silently overwrite them."""
    result = {}
    duplicates = []
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in result:
            duplicates.append(key)
        result[key] = row
    if duplicates:
        raise ValueError(f"{label}: duplicate keys: {duplicates[:5]!r}")
    return result


def verify_pair_inventory(rows, expected):
    """Compare identities as sets, then truth/uptake values; never counts alone."""
    keys = ('condition_id', 'task_id', 'repetition', 'expression', 'recipient')
    actual = unique_index(rows, keys, 'exposure inventory')
    missing, unexpected = set(expected) - set(actual), set(actual) - set(expected)
    if missing or unexpected:
        raise ValueError(f"exposure inventory: missing={sorted(missing)[:5]!r}; unexpected={sorted(unexpected)[:5]!r}")
    for key, row in actual.items():
        value = (row['information_type'], int(row['adopted']))
        if value != expected[key]:
            raise ValueError(f"exposure inventory: value mismatch for {key!r}: {value!r} != {expected[key]!r}")
    return actual

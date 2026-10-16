import ast
import math
import operator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def _eval(node, env):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError('Unsupported constant in equation')
    if isinstance(node, ast.Name):
        if node.id in env:
            return float(env[node.id])
        raise ValueError('Unknown variable: {}'.format(node.id))
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError('Unsupported operator in equation')
        return op(_eval(node.left, env), _eval(node.right, env))
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_eval(node.operand, env)
        if isinstance(node.op, ast.UAdd):
            return +_eval(node.operand, env)
        raise ValueError('Unsupported unary operator in equation')
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == 'sqrt' and len(node.args) == 1:
            val = _eval(node.args[0], env)
            if val < 0:
                raise ValueError('sqrt of a negative number')
            return math.sqrt(val)
        raise ValueError('Unsupported function call in equation')
    raise ValueError('Unsupported expression in equation')


def evaluate_equation(equation, variables):
    """Safely evaluate a numeric equation with a whitelisted variable set.

    Supports numbers, + - * / ** % and sqrt(). Unsupported syntax raises
    ValueError instead of executing arbitrary code.
    """
    if not equation or not equation.strip():
        raise ValueError('No equation defined')
    tree = ast.parse(equation, mode='eval')
    return _eval(tree, variables)